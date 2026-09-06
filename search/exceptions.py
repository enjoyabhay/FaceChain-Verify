"""Exceptions shared by every search backend (vision_api, serpapi_search, ...)."""
from __future__ import annotations


class SearchConfigError(Exception):
    """Raised when the search backend isn't configured (e.g. missing API key)."""


class NoMatchFoundError(Exception):
    """Raised when the web search ran but found no matching pages."""
