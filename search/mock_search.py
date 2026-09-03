"""Mock reverse-image-search backend.

Used only when the pipeline is run with --mock-search, so the rest of the
pipeline (hashing + blockchain anchoring + verification) can be exercised
without a Google Vision API key. Never presented as a real search result.
"""
from __future__ import annotations

from typing import Dict, Optional


def mock_web_detect(image_path: str) -> Dict[str, Optional[str]]:
    return {
        "post_url": "https://example.com/mock-social-post",
        "page_title": "[MOCK] Example matching post -- no real search was performed",
        "matched_image_url": "https://example.com/mock-matched-image.jpg",
        "is_social": False,
        "total_pages_found": 0,
        "mock": True,
    }
