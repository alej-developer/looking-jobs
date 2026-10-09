"""Plain-text helpers. Job descriptions from ATS APIs often contain HTML."""

from __future__ import annotations

import re

_TAG = re.compile(r"<[^>]*>")
_SPACE = re.compile(r"\s+")


def plain_text(value: str, *, limit: int) -> str:
    """Drop tags and collapse whitespace, then cap the length."""
    text = _TAG.sub(" ", value)
    text = _SPACE.sub(" ", text).strip()
    return text[:limit]
