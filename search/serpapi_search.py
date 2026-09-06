"""Reverse image search via SerpApi's Google Reverse Image engine.

Unlike Google Cloud Vision (which accepts image bytes directly in the
request body), SerpApi doesn't accept a raw file upload -- it's automating
Google's own reverse-image search UI, which requires a URL to an image
that's already publicly reachable.

So this module: 1) uploads the face crop to the caller's own Dropbox App
folder and creates a shared link, 2) runs the SerpApi search against that
link, then 3) deletes the upload immediately afterward, whether the search
succeeded or not -- to keep the public-exposure window as short as
possible. Dropbox (rather than an anonymous temp-file host) was chosen
because plenty of networks -- notably ones behind corporate proxies --
block the entire "anonymous file/image hosting" category outright, while
mainstream productivity tools like Dropbox are typically allowed. Both
Dropbox and SerpApi have genuine free tiers with no billing/card required.

Privacy note: this means the face crop is briefly reachable at a public
(but unguessable) URL during the search, unlike the Vision API backend.
Only use this on images you have the right to use, per the project's
disclaimer.

Docs: https://serpapi.com/google-reverse-image
      https://www.dropbox.com/developers/documentation/http/documentation
"""
from __future__ import annotations

import json
import os
import secrets
from typing import Dict, Optional, Tuple

import requests

from search.exceptions import NoMatchFoundError, SearchConfigError
from search.social_domains import is_social

SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
DROPBOX_UPLOAD_ENDPOINT = "https://content.dropboxapi.com/2/files/upload"
DROPBOX_SHARE_ENDPOINT = "https://api.dropboxapi.com/2/sharing/create_shared_link_with_settings"
DROPBOX_DELETE_ENDPOINT = "https://api.dropboxapi.com/2/files/delete_v2"


def _dropbox_token() -> str:
    token = os.environ.get("DROPBOX_ACCESS_TOKEN")
    if not token:
        raise SearchConfigError(
            "DROPBOX_ACCESS_TOKEN is not set. The 'serpapi' search provider "
            "needs somewhere public to host the face crop temporarily (SerpApi "
            "only accepts an image URL, not a direct upload). Create a free "
            "Dropbox app at https://www.dropbox.com/developers/apps (Scoped "
            "access, with files.content.write / files.content.read / "
            "sharing.write permissions), generate an access token on the "
            "app's page, and put it in .env."
        )
    return token


def _upload_to_dropbox(image_path: str) -> Tuple[str, str]:
    """Uploads the face crop to the caller's Dropbox App folder and creates
    a public shared link. Returns (raw_image_url, remote_path) so the
    caller can delete it afterward."""
    token = _dropbox_token()
    remote_path = f"/facechain_tmp/{secrets.token_hex(12)}.jpg"

    with open(image_path, "rb") as f:
        content = f.read()

    upload_resp = requests.post(
        DROPBOX_UPLOAD_ENDPOINT,
        headers={
            "Authorization": f"Bearer {token}",
            "Dropbox-API-Arg": json.dumps({"path": remote_path, "mode": "overwrite"}),
            "Content-Type": "application/octet-stream",
        },
        data=content,
        timeout=30,
    )
    if not upload_resp.ok:
        raise SearchConfigError(f"Dropbox upload failed ({upload_resp.status_code}): {upload_resp.text}")

    share_resp = requests.post(
        DROPBOX_SHARE_ENDPOINT,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={"path": remote_path},
        timeout=30,
    )
    if not share_resp.ok:
        raise SearchConfigError(
            f"Dropbox share-link creation failed ({share_resp.status_code}): {share_resp.text}"
        )

    share_url = share_resp.json()["url"]
    # Dropbox's default shared link serves an HTML preview page; "raw=1"
    # makes it serve the actual file bytes instead, which is what SerpApi's
    # fetcher needs.
    raw_url = share_url.replace("?dl=0", "").split("?")[0] + "?raw=1"

    return raw_url, remote_path


def _delete_from_dropbox(remote_path: str) -> None:
    try:
        token = os.environ.get("DROPBOX_ACCESS_TOKEN")
        if not token:
            return
        requests.post(
            DROPBOX_DELETE_ENDPOINT,
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"path": remote_path},
            timeout=15,
        )
    except requests.RequestException:
        pass  # best-effort cleanup -- not fatal if it fails


def web_detect(image_path: str, max_results: int = 15) -> Dict[str, Optional[str]]:
    """Run a real reverse image search for the face crop at `image_path`
    via SerpApi, and return the best-matching social/web post found.

    Returns a dict: {post_url, page_title, matched_image_url, is_social, total_pages_found}
    """
    api_key = os.environ.get("SERPAPI_API_KEY")
    if not api_key:
        raise SearchConfigError(
            "SERPAPI_API_KEY is not set. Sign up for a free plan at "
            "https://serpapi.com/ and put your key in .env."
        )

    image_url, remote_path = _upload_to_dropbox(image_path)
    try:
        resp = requests.get(
            SERPAPI_ENDPOINT,
            params={
                "engine": "google_reverse_image",
                "image_url": image_url,
                "api_key": api_key,
            },
            timeout=30,
        )
        if not resp.ok:
            raise SearchConfigError(f"SerpApi request failed ({resp.status_code}): {resp.text}")

        data = resp.json()
        if "error" in data:
            raise SearchConfigError(f"SerpApi error: {data['error']}")

        results = data.get("image_results", [])[:max_results]
        if not results:
            raise NoMatchFoundError(
                "SerpApi ran successfully but found no matching web pages for this image."
            )

        best = next((r for r in results if is_social(r.get("link", ""))), results[0])

        return {
            "post_url": best.get("link", ""),
            "page_title": best.get("title", ""),
            "matched_image_url": best.get("thumbnail") or best.get("original", ""),
            "is_social": is_social(best.get("link", "")),
            "total_pages_found": len(results),
        }
    finally:
        _delete_from_dropbox(remote_path)
