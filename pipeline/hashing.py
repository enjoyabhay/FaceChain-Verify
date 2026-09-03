"""Canonical hashing for on-chain records.

Uses Keccak-256 (the pre-NIST-standardization variant, via pycryptodome's
`Crypto.Hash.keccak`) so it matches Solidity's `keccak256` byte-for-byte --
NOT the NIST SHA3-256 variant, which uses different padding and would
produce a different digest.
"""
from __future__ import annotations

from Crypto.Hash import keccak


def compute_record_hash(
    face_image_bytes: bytes, post_url: str, matched_image_url: str, timestamp: int
) -> str:
    """Compute the record fingerprint anchored on-chain.

    payload = face_image_bytes || "|" || post_url || "|" || matched_image_url || "|" || timestamp
    """
    payload = (
        face_image_bytes
        + b"|"
        + post_url.encode("utf-8")
        + b"|"
        + matched_image_url.encode("utf-8")
        + b"|"
        + str(int(timestamp)).encode("utf-8")
    )
    h = keccak.new(digest_bits=256)
    h.update(payload)
    return "0x" + h.hexdigest()
