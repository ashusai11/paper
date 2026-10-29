"""Thin wrapper over firecrawl-anydoc: document -> cleaned Markdown.

Whole files go through the path API (anydoc.to_markdown), which detects format
from content with extension fallback — necessary because signature-less formats
like CSV cannot be detected from bytes alone. Split PDF pages go through the
bytes API with the format named explicitly.
"""

import importlib.metadata

import anydoc

from agent1_offline.utils.text_cleaner import clean_text


class AnyDocError(Exception):
    """Raised when AnyDoc cannot convert the given document."""


try:
    ANYDOC_VERSION = importlib.metadata.version("firecrawl-anydoc")
except importlib.metadata.PackageNotFoundError:  # pragma: no cover
    ANYDOC_VERSION = "unknown"


def markdown_from_path(path) -> str:
    """Convert a document file to cleaned GitHub-Flavored Markdown.
    Raises AnyDocError on any conversion failure."""
    try:
        markdown = anydoc.to_markdown(str(path))
    except Exception as exc:  # MalformedError/UnsupportedError/EncryptedError/...
        raise AnyDocError(str(exc)) from exc
    return clean_text(markdown)


def markdown_from_bytes(data: bytes, fmt: str | None = None) -> str:
    """Convert in-memory document bytes to cleaned GitHub-Flavored Markdown.
    `fmt` names the format explicitly, which signature-less formats require.
    Raises AnyDocError on any conversion failure."""
    try:
        markdown = anydoc.to_markdown_bytes(data, fmt)
    except Exception as exc:
        raise AnyDocError(str(exc)) from exc
    return clean_text(markdown)
