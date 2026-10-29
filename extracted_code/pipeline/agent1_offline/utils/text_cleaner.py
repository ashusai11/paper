"""Deterministic whitespace/artifact normalization applied to all extracted text."""

import re

_TRAILING_WS = re.compile(r"[ \t]+(\n|$)")
_MANY_BLANKS = re.compile(r"\n{3,}")


def clean_text(text: str) -> str:
    """Normalize extracted text: unify newlines, drop trailing spaces, and
    collapse 3+ blank lines to a single blank line. Returns "" for input that
    is empty or whitespace-only."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.replace("\u00a0", " ")
    text = _TRAILING_WS.sub(r"\1", text)
    text = _MANY_BLANKS.sub("\n\n", text)
    return text.strip()
