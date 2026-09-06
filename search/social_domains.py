"""Shared list of recognized social media domains, used by every search
backend to rank a "real social media post" above a generic web page."""
from __future__ import annotations

SOCIAL_DOMAINS = [
    "instagram.com",
    "twitter.com",
    "x.com",
    "facebook.com",
    "linkedin.com",
    "reddit.com",
    "tiktok.com",
    "pinterest.com",
    "threads.net",
    "vk.com",
]


def is_social(url: str) -> bool:
    return any(domain in url.lower() for domain in SOCIAL_DOMAINS)
