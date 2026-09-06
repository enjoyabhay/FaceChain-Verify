# Running FaceChain Verify with a Real Photo (Real Search, No Payment)

This assumes you've already done the one-time setup -- Python venv
created, dependencies installed (`pip install -r requirements.txt`, or the
OpenCV-fallback subset if `dlib` failed to build), and `chain\` npm
dependencies installed (`cd chain && npm install`). This file covers
getting a **real** (non-mock, non-paid) search working end to end, and
running it.

This project supports two real search backends:

- **`google`** (Google Cloud Vision) -- highest quality, but Google
  requires billing/a card enabled on the project even for the free tier.
- **`serpapi`** (SerpApi's Google Reverse Image search) -- **no
  billing/card required**. This is the recommended path if you don't want
  to enter payment details anywhere. It's the default in `.env.example`.

The rest of this file covers the `serpapi` path.

## Why SerpApi alone isn't enough: the Dropbox step

SerpApi doesn't accept a direct image upload -- it needs a public URL to
fetch the image from (it's automating Google's own reverse-image search
UI). Free anonymous file-hosting services (0x0.st, catbox.moe, imgur,
imgbb, etc.) are commonly blocked outright by corporate network security
policies as a whole category, so this project instead uses **your own free
Dropbox account** as the temporary host: it uploads the face crop to a
Dropbox app folder, creates a shared link, runs the SerpApi search, then
**deletes the upload immediately afterward**. Dropbox is free with no card
required, and is not the kind of site corporate proxies typically block.

Note: some corporate networks block *outbound uploads* specifically (a
Data-Loss-Prevention policy), even to mainstream services like Dropbox,
while still allowing normal browsing to those same sites. If you hit that,
the fix isn't a different image host -- it's running from a different
network (e.g. home wifi or a mobile hotspot) for the parts of this project
that upload data (Dropbox search, and `git push`).

## Step 1: Get a free SerpApi key

1. Sign up at https://serpapi.com/ (free plan, no card required as of
   writing -- double check at signup in case that's changed).
2. Copy your API key from the dashboard.

## Step 2: Get a free Dropbox access token

1. Go to https://www.dropbox.com/developers/apps and log in (or create a
   free Dropbox account first if you don't have one).
2. Click **Create app**.
3. Choose **Scoped access**, then **App folder** (so it only gets access
   to its own folder, not your whole Dropbox).
4. Give it any name (e.g. `facechain-verify`).
5. On the app's page, go to the **Permissions** tab and enable:
   - `files.content.write`
   - `files.content.read`
   - `sharing.write`
   Click **Submit** to save.
6. Go back to the **Settings** tab, find **OAuth 2 / Generated access
   token**, and click **Generate**. Copy the token shown.

This whole process is free and doesn't ask for a card at any point.

## Step 3: Put both keys in `.env`

Open `.env` in the project root and fill in:

```
SEARCH_PROVIDER=serpapi
SERPAPI_API_KEY=<your SerpApi key>
DROPBOX_ACCESS_TOKEN=<your Dropbox access token>
```

## Step 4: Open a terminal in the project folder and activate the venv

```powershell
cd "C:\Users\abhaya.agrawal\OneDrive - Fractal Analytics Limited\Desktop\task 3"
.\.venv\Scripts\Activate.ps1
```

You should see `(.venv)` appear at the start of your prompt.

## Step 5: Add a real photo you have the rights to use

```powershell
Copy-Item "C:\path\to\your\photo.jpg" "sample_images\me.jpg"
```

Notes on picking a good test photo:
- It must be a photo you own or have explicit consent to use (see the
  disclaimer the tool prints on every run).
- Use a photo that's actually posted somewhere public (your own
  Instagram/LinkedIn/Twitter profile photo, for example) -- the search can
  only find what's already indexed on the public web.

## Step 6: Run the pipeline for real

```powershell
python main.py sample_images\me.jpg
```

(No `--search-provider` flag needed if `SEARCH_PROVIDER=serpapi` is set in
`.env` -- that's already the default there.)

## Step 7: What you should see

```
FaceChain Verify is a research/demo tool.
Only run it on images you own or have explicit consent to use...

[1/4] Detecting face in sample_images\me.jpg ...
      face detected via 'opencv_haar', crop saved to ...\output\face_crop.png
[2/4] Searching the web for a matching post ...
      using search provider: serpapi
      best match: <a real URL, ideally a social media link>
      page title: <the real page's title>
[3/4] Anchoring record on-chain (network=localhost) ...
      started local Hardhat node on 127.0.0.1:8545
      contract deployed at 0x...
      tx hash: 0x...  (record id 0)
[4/4] Re-fetching the on-chain record and verifying the fingerprint ...

=== SUMMARY ===
...
VERIFICATION RESULT: PASS
```

## Step 8 (optional): Anchor on the public Polygon Amoy testnet instead

By default the record is anchored on a local, disposable blockchain (fast,
free, no setup). To anchor on a real public testnet instead:

1. A free RPC URL for Amoy -- the default in `.env.example`
   (`https://rpc-amoy.polygon.technology`) usually works as-is.
2. A funded testnet account: get free test MATIC from
   https://faucet.polygon.technology/, then put that account's private key
   in `.env` as `CHAIN_PRIVATE_KEY=...` (never use a real/mainnet key here).
3. Run with `--network amoy`:

```powershell
python main.py sample_images\me.jpg --network amoy
```

This takes longer (real network confirmation times) and can fail if the
testnet or faucet is having issues -- that's expected/normal for a public
testnet, not a bug in the project. The local run in Step 6 is the more
reliable one to record for your submission if you want a guaranteed smooth
take.

## Troubleshooting

- **`SERPAPI_API_KEY is not set`** / **`DROPBOX_ACCESS_TOKEN is not set`**:
  check `.env` has both values filled in, no quotes, no extra spaces.
- **Dropbox upload/share-link errors**: double-check the app's Permissions
  tab actually has `files.content.write`, `files.content.read`, and
  `sharing.write` enabled and saved -- a token generated before adding a
  permission won't have it; generate a new token after saving permissions.
- **Dropbox upload fails with a corporate-network block page (e.g.
  mentions "Zscaler" or "not allowed to upload files")**: this is your
  network's Data-Loss-Prevention policy blocking outbound uploads, not a
  bug. Try from a different network (home wifi, mobile hotspot).
- **`SSLError: [SSL: CERTIFICATE_VERIFY_FAILED] ... unable to get local
  issuer certificate`**: your network is behind a corporate proxy (e.g.
  Zscaler) that inspects HTTPS traffic with its own certificate, which
  Python doesn't trust by default even though your OS/browser already
  does. Fix it once with:
  ```powershell
  pip install pip-system-certs
  ```
  No code or `.env` changes needed -- just rerun the command after
  installing it. (Already in `requirements.txt` for future installs.)
- **"SerpApi ran successfully but found no matching web pages"**: the
  photo isn't indexed anywhere Google's crawled -- try a photo that's
  actually posted publicly somewhere.
- **`dlib`/`face_recognition` fails to build**: expected without a C++
  build toolchain. Install everything else individually instead:
  ```powershell
  pip install opencv-python==4.10.0.84 Pillow==10.4.0 numpy requests==2.32.3 pycryptodome==3.20.0 python-dotenv==1.0.1 pip-system-certs
  ```
  The pipeline automatically falls back to OpenCV for face detection.
- **`HH502: Couldn't download compiler version list`**: usually a
  transient network blip -- just retry the same command.
- **Port 8545 already in use**: something else (maybe a leftover Hardhat
  node) is using it. Close it, or run with `--network amoy` instead.

For architecture/design details, see [README.md](README.md).
