"""Orchestrates the full FaceChain Verify pipeline:

  face photo -> face detection/encoding -> reverse image search
             -> keccak256 fingerprint -> on-chain anchor -> on-chain re-verify
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Optional

import requests

from face.detect import detect_face
from pipeline.hashing import compute_record_hash
from search.mock_search import mock_web_detect
from search.serpapi_search import web_detect as serpapi_web_detect
from search.vision_api import web_detect as google_web_detect

SEARCH_BACKENDS = {
    "google": google_web_detect,
    "serpapi": serpapi_web_detect,
}

ROOT = Path(__file__).resolve().parent.parent
CHAIN_DIR = ROOT / "chain"
OUTPUT_DIR = ROOT / "output"

HARDHAT_NODE_HOST = "127.0.0.1"
HARDHAT_NODE_PORT = 8545


def _npx_executable() -> str:
    npx = shutil.which("npx")
    if not npx:
        raise RuntimeError(
            "npx not found on PATH. Install Node.js (https://nodejs.org/) to run "
            "the blockchain steps."
        )
    return npx


def _stop_process_tree(proc: subprocess.Popen) -> None:
    """`npx` spawns node as a child process; Popen.terminate() only signals
    the npx wrapper on Windows and leaves the actual Hardhat node running
    (still holding port 8545). Kill the whole tree instead."""
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            capture_output=True,
        )
    else:
        proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def _rpc_is_ready(host: str, port: int) -> bool:
    """A TCP connect succeeding isn't enough -- the JSON-RPC handler can
    still be a moment behind the listening socket. Poll with a real
    eth_chainId call so we don't hand off to a server that isn't actually
    answering requests yet."""
    try:
        resp = requests.post(
            f"http://{host}:{port}",
            json={"jsonrpc": "2.0", "method": "eth_chainId", "params": [], "id": 1},
            timeout=1,
        )
        return resp.status_code == 200 and "result" in resp.json()
    except requests.RequestException:
        return False


def _start_local_node() -> Optional[subprocess.Popen]:
    """Start `npx hardhat node` in the background if nothing is already
    answering JSON-RPC on the local port. Returns the Popen handle, or None
    if a node was already running (in which case we don't own its lifecycle)."""
    if _rpc_is_ready(HARDHAT_NODE_HOST, HARDHAT_NODE_PORT):
        return None

    # Hardhat logs every JSON-RPC call it receives. If we pipe stdout and
    # never read it, the pipe buffer fills up and Node's write() calls start
    # blocking -- which stalls the single-threaded event loop and makes the
    # "running" node stop answering RPC requests entirely. Route output to a
    # file instead so writes never block on a reader.
    OUTPUT_DIR.mkdir(exist_ok=True)
    log_path = OUTPUT_DIR / "hardhat_node.log"
    log_file = open(log_path, "w")
    proc = subprocess.Popen(
        [_npx_executable(), "hardhat", "node"],
        cwd=str(CHAIN_DIR),
        stdout=log_file,
        stderr=subprocess.STDOUT,
    )
    for _ in range(60):
        if _rpc_is_ready(HARDHAT_NODE_HOST, HARDHAT_NODE_PORT):
            return proc
        if proc.poll() is not None:
            log_file.close()
            output = log_path.read_text(errors="replace")
            raise RuntimeError(f"Local Hardhat node exited early:\n{output}")
        time.sleep(0.5)

    _stop_process_tree(proc)
    raise RuntimeError(
        f"Timed out waiting for local Hardhat node to start on port 8545 "
        f"(see {log_path} for its output)"
    )


def _run_node_script(script_rel_path: str, network: str, env_extra: Optional[dict] = None) -> dict:
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    cmd = [_npx_executable(), "hardhat", "run", script_rel_path, "--network", network]
    result = subprocess.run(
        cmd, cwd=str(CHAIN_DIR), env=env, capture_output=True, text=True
    )
    if result.returncode != 0:
        raise RuntimeError(f"Node script failed ({script_rel_path}):\n{result.stderr or result.stdout}")

    lines = [line for line in result.stdout.strip().splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"No output from {script_rel_path}:\n{result.stderr}")

    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse JSON output from {script_rel_path}:\n{result.stdout}") from exc


def run_pipeline(
    image_path: str,
    network: str = "localhost",
    mock_search: bool = False,
    keep_node: bool = False,
    search_provider: str = "google",
) -> dict:
    OUTPUT_DIR.mkdir(exist_ok=True)

    print(f"[1/4] Detecting face in {image_path} ...")
    face_result = detect_face(image_path, str(OUTPUT_DIR))
    print(f"      face detected via '{face_result.method}', crop saved to {face_result.face_image_path}")

    print("[2/4] Searching the web for a matching post ...")
    if mock_search:
        print("      (--mock-search: skipping the real search call)")
        match = mock_web_detect(face_result.face_image_path)
    else:
        print(f"      using search provider: {search_provider}")
        match = SEARCH_BACKENDS[search_provider](face_result.face_image_path)
    print(f"      best match: {match['post_url']}")
    if match.get("page_title"):
        print(f"      page title: {match['page_title']}")

    timestamp = int(time.time())
    with open(face_result.face_image_path, "rb") as f:
        face_bytes = f.read()

    data_hash = compute_record_hash(
        face_bytes, match["post_url"], match.get("matched_image_url") or "", timestamp
    )

    print(f"[3/4] Anchoring record on-chain (network={network}) ...")
    node_proc = None
    try:
        if network == "localhost":
            node_proc = _start_local_node()
            if node_proc:
                print(f"      started local Hardhat node on {HARDHAT_NODE_HOST}:{HARDHAT_NODE_PORT}")
            else:
                print(f"      reusing existing node on {HARDHAT_NODE_HOST}:{HARDHAT_NODE_PORT}")

        deploy_result = _run_node_script("scripts/deploy.js", network)
        print(f"      contract deployed at {deploy_result['address']}")

        record_result = _run_node_script(
            "scripts/addRecord.js",
            network,
            env_extra={
                "DATA_HASH": data_hash,
                "POST_URL": match["post_url"],
                "MATCHED_IMAGE_URL": match.get("matched_image_url") or "",
                "TIMESTAMP": str(timestamp),
            },
        )
        print(f"      tx hash: {record_result['txHash']}  (record id {record_result['recordId']})")

        print("[4/4] Re-fetching the on-chain record and verifying the fingerprint ...")
        verify_result = _run_node_script(
            "scripts/verifyRecord.js",
            network,
            env_extra={"RECORD_ID": record_result["recordId"]},
        )

        recomputed_hash = compute_record_hash(
            face_bytes,
            verify_result["postUrl"],
            verify_result["matchedImageUrl"],
            int(verify_result["timestamp"]),
        )
        verification_passed = recomputed_hash.lower() == verify_result["dataHash"].lower()

        summary = {
            "face_method": face_result.method,
            "matched_post_url": match["post_url"],
            "matched_image_url": match.get("matched_image_url") or "",
            "search_mock": mock_search,
            "search_provider": search_provider if not mock_search else "mock",
            "network": network,
            "contract_address": deploy_result["address"],
            "tx_hash": record_result["txHash"],
            "record_id": record_result["recordId"],
            "on_chain_hash": verify_result["dataHash"],
            "recomputed_hash": recomputed_hash,
            "verification_passed": verification_passed,
        }

        print("\n=== SUMMARY ===")
        for key, value in summary.items():
            print(f"{key}: {value}")
        print(f"\nVERIFICATION RESULT: {'PASS' if verification_passed else 'FAIL'}")

        return summary
    finally:
        if node_proc and not keep_node:
            _stop_process_tree(node_proc)
