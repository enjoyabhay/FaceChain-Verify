# FaceChain Verify

An end-to-end pipeline that takes a face photo, finds a real matching post
on the web/social media via reverse image search, and anchors that
discovery on a blockchain as a tamper-evident, re-verifiable record.

```
face photo -> face detection/encoding -> reverse image search (real match)
           -> keccak256 fingerprint -> on-chain anchor -> on-chain re-verify
```

> **Disclaimer:** This is a research/demo tool built for a hackathon. Only
> run it on images you own or have explicit consent to use. Do not use it
> to identify, track, or profile other people without their consent. No
> raw biometric data is ever written to the blockchain -- only a
> cryptographic hash.

## Architecture

```
                 ┌───────────────────┐
  face photo --> │  face/detect.py    │  face_recognition (dlib) or
                 │                    │  OpenCV Haar cascade fallback
                 └─────────┬──────────┘
                           │ cropped face image
                           v
                 ┌────────────────────┐
                 │ search/vision_api.py│  Google Cloud Vision
                 │                    │  "Web Detection" (live search)
                 └─────────┬──────────┘
                           │ matched post URL + matched image URL
                           v
                 ┌────────────────────┐
                 │ pipeline/hashing.py │  keccak256(face bytes ||
                 │                    │  postUrl || imageUrl || timestamp)
                 └─────────┬──────────┘
                           │ dataHash
                           v
                 ┌────────────────────┐
                 │ chain/ (Hardhat +   │  FaceMatchRegistry.sol
                 │ ethers.js)          │  addRecord() -> tx on-chain
                 └─────────┬──────────┘
                           │ recordId
                           v
                 ┌────────────────────┐
                 │ verifyRecord.js     │  read record back from chain,
                 │                    │  recompute hash locally, compare
                 └────────────────────┘
                           │
                           v
                 PASS / FAIL verification result
```

Everything is orchestrated by [`main.py`](main.py) / [`pipeline/pipeline.py`](pipeline/pipeline.py),
which runs each stage in order and prints progress + a final summary.

## Why these technology choices

- **Face detection: `face_recognition` (dlib) with an OpenCV Haar cascade
  fallback.** `face_recognition` gives both a bounding box and a 128-d
  embedding with a couple of lines of code; the OpenCV fallback keeps the
  pipeline runnable even where dlib's C++ build toolchain isn't available
  (see Known Limitations).

- **Reverse image search: Google Cloud Vision "Web Detection".** Unlike
  face-search-specific services (many of which have ToS/ethics problems
  for this kind of demo), Vision's Web Detection is a legitimate, publicly
  documented Google API purpose-built for "does this image appear
  elsewhere on the web," with a free tier (1000 units/month) and no
  scraping involved. It returns real pages where the image (or a visually
  similar one) appears, which we rank to prefer known social media
  domains. `search/vision_api.py` is written as a small, swappable module;
  SerpApi's Google Lens endpoint is a documented drop-in alternative if
  you'd rather use that (see below).

- **Blockchain: a Solidity registry contract via Hardhat + ethers.js,
  runnable locally or on Polygon's Amoy testnet.** A local Hardhat node
  makes the on-chain steps fast and 100% reliable for a live demo (no
  faucet, no network flakiness). The exact same contract and scripts also
  deploy to Polygon Amoy (a free public testnet) so you can show a real,
  publicly verifiable transaction on a block explorer if you want that for
  judging. Only a hash + the discovered post's public metadata are stored
  on-chain -- never the raw face image or embedding.

## Repo structure

```
face/               face detection + encoding
search/              reverse image search (real API + mock)
chain/               Solidity contract + Hardhat config + deploy/anchor/verify scripts
pipeline/            hashing + orchestration
main.py              CLI entrypoint
sample_images/        where to put a test photo (none bundled, see below)
output/               generated face crops (gitignored)
```

## Setup

### 1. Python side

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

`face_recognition` depends on `dlib`, which needs a C++ build toolchain and
CMake to compile from source. If `pip install -r requirements.txt` fails on
dlib:

- **Windows:** install "Desktop development with C++" via the Visual Studio
  Build Tools, and CMake, then retry -- or install dlib via conda
  (`conda install -c conda-forge dlib`) and pip-install the rest.
- **macOS:** `brew install cmake` first.
- **Linux:** `sudo apt install build-essential cmake`.
- If you'd rather skip this entirely, do nothing extra -- the pipeline
  automatically falls back to OpenCV's Haar cascade for face detection if
  `face_recognition`/dlib isn't importable (see Known Limitations).

### 2. Blockchain side

Requires Node.js 18+.

```bash
cd chain
npm install
npx hardhat compile
cd ..
```

### 3. Configure environment

```bash
cp .env.example .env
```

Then fill in:

- `GOOGLE_VISION_API_KEY` -- from Google Cloud Console: create/select a
  project, enable **Cloud Vision API**, then create an API key under
  *APIs & Services > Credentials*. Free tier covers plenty of hackathon
  demo runs. Not required if you only run with `--mock-search`.
- `AMOY_RPC_URL` / `CHAIN_PRIVATE_KEY` -- only needed for `--network amoy`.
  Get free test MATIC from https://faucet.polygon.technology/. **Never**
  put a mainnet private key here.

## Running it

A bundled, AI-generated (non-real-person) test image lets you try the whole
pipeline with zero setup: `sample_images/synthetic_test_face.jpg`. For a
genuine web/social match, swap in a photo you have rights to use -- see
[`sample_images/README.md`](sample_images/README.md).

**Try it immediately, no API key needed** (uses a labeled mock search result
so you can still exercise face detection + blockchain anchoring +
verification end to end):

```bash
python main.py sample_images/synthetic_test_face.jpg --mock-search
```

**Full pipeline with a real reverse image search** (needs
`GOOGLE_VISION_API_KEY` and a real photo you have rights to use):

```bash
python main.py sample_images/me.jpg
```

**Anchor on the public Polygon Amoy testnet instead of a local node:**

```bash
python main.py sample_images/me.jpg --network amoy
```

This will, in order:

1. Detect and crop the face, save it to `output/face_crop.png`.
2. Run a live Google Vision Web Detection search and pick the best social
   media match.
3. Compute `keccak256(face_bytes || postUrl || matchedImageUrl || timestamp)`.
4. Spin up a local Hardhat node (if `--network localhost` and one isn't
   already running), deploy `FaceMatchRegistry`, and submit the record.
5. Read the record back from the chain, recompute the hash locally from
   the on-chain data + the original face bytes, and print **PASS**/**FAIL**
   depending on whether they match.

## How the on-chain verification works

The contract (`chain/contracts/FaceMatchRegistry.sol`) stores, per record:
`dataHash`, `postUrl`, `matchedImageUrl`, `timestamp`, and the submitting
address. `dataHash` is computed **off-chain**, in Python, over the
concatenation of the face image bytes and the discovered post's metadata --
this keeps raw biometric data off the chain entirely while still tying the
on-chain record cryptographically to the exact face image that produced it.

To verify: `verifyRecord.js` reads the stored `postUrl`, `matchedImageUrl`,
`timestamp`, and `dataHash` back from the chain. The Python side then
recomputes the hash locally using those values plus the original (locally
cached) face bytes, and compares it to the on-chain `dataHash`. If anyone
tampered with the on-chain metadata, or if the wrong face image were
substituted, the recomputed hash would not match -- that mismatch is what
makes the record tamper-evident.

## Known limitations

- **Reverse image search coverage** is bounded by what Google's index has
  crawled; a real post may exist but not be found if it's unindexed,
  private, or was posted very recently.
- **Face recognition accuracy** depends on image quality, angle, and
  lighting; the OpenCV Haar cascade fallback (used only if dlib isn't
  installed) is noticeably less accurate than `face_recognition` and does
  not produce an embedding, only a bounding box.
- **Testnet reliability**: Polygon Amoy is a public testnet -- faucets can
  run dry and RPC endpoints can rate-limit or lag. The local Hardhat
  network exists specifically so the demo doesn't depend on this.
- **The on-chain record stores plaintext metadata** (post URL, matched
  image URL, timestamp) -- these are not private on a public chain; only
  the face image itself is kept off-chain.
- **This is not an identity-verification or KYC system.** A "match" is a
  visual similarity result from a third-party API, not a legal proof of
  identity.
- `dlib`/`face_recognition` can be nontrivial to install on some machines
  (see Setup); the OpenCV fallback exists so the pipeline still runs.
- **Corporate networks / proxies**: some proxies (e.g. Zscaler) block direct
  `.exe` downloads, which breaks Hardhat's default native-binary solc fetch
  on Windows. `chain/hardhat.config.js` loads `chain/scripts/force-wasm-solc.cjs`
  by default, which makes Hardhat use the solc-js/wasm compiler (a plain
  `.js` download) instead -- this works on every OS and network we tested,
  at the cost of a slightly slower first compile.

## License

MIT (see contract header). Use responsibly.
