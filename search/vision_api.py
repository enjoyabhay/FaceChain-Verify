"""Reverse image search via the Google Cloud Vision "Web Detection" feature.

This calls the REST `images:annotate` endpoint directly (with a plain API
key) rather than the google-cloud-vision SDK, so setup is just "enable the
Vision API + create an API key" -- no service-account JSON required.

Docs: https://cloud.google.com/vision/docs/detecting-web
"""
from __future__ import annotations

import base64
import os
from typing import Dict, List, Optional

import requests

from search.exceptions import NoMatchFoundError, SearchConfigError
from search.social_domains import is_social

VISION_ENDPOINT = "https://vision.googleapis.com/v1/images:annotate"


def _pick_best_page(pages: List[Dict]) -> Dict:
    """The API already returns pages ordered by relevance; prefer the
    highest-ranked page that's on a recognized social media domain, and
    fall back to the top overall result otherwise."""
    for page in pages:
        if is_social(page.get("url", "")):
            return page
    return pages[0]


def _first_matching_image_url(page: Dict) -> str:
    for key in ("fullMatchingImages", "partialMatchingImages"):
        images = page.get(key) or []
        if images:
            return images[0].get("url", "")
    return ""


def web_detect(image_path: str, max_results: int = 15) -> Dict[str, Optional[str]]:
    """Run a real reverse image search for the face crop at `image_path`
    and return the best-matching social/web post found.

    Returns a dict: {post_url, page_title, matched_image_url, all_matches}
    """
    api_key = os.environ.get("GOOGLE_VISION_API_KEY")
    if not api_key:
        raise SearchConfigError(
            "GOOGLE_VISION_API_KEY is not set. Create one in Google Cloud "
            "Console (enable 'Cloud Vision API' first) and put it in your .env."
        )

    with open(image_path, "rb") as f:
        content = base64.b64encode(f.read()).decode("utf-8")

    payload = {
        "requests": [
            {
                "image": {"content": content},
                "features": [{"type": "WEB_DETECTION", "maxResults": max_results}],
            }
        ]
    }

    resp = requests.post(f"{VISION_ENDPOINT}?key={api_key}", json=payload, timeout=30)
    if not resp.ok:
        try:
            detail = resp.json().get("error", {}).get("message", resp.text)
        except ValueError:
            detail = resp.text
        raise SearchConfigError(
            f"Vision API request failed ({resp.status_code}): {detail}"
        )
    data = resp.json()

    response0 = data.get("responses", [{}])[0]
    if "error" in response0:
        raise SearchConfigError(f"Vision API error: {response0['error'].get('message')}")

    web_detection = response0.get("webDetection", {})
    pages = web_detection.get("pagesWithMatchingImages", [])

    if not pages:
        raise NoMatchFoundError(
            "Vision API ran successfully but found no matching web pages for this image."
        )

    best = _pick_best_page(pages)

    return {
        "post_url": best.get("url", ""),
        "page_title": best.get("pageTitle", ""),
        "matched_image_url": _first_matching_image_url(best),
        "is_social": is_social(best.get("url", "")),
        "total_pages_found": len(pages),
    }
