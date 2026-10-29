"""Document format detection via AnyDoc: content first, extension as fallback.

Content-only detection is not sufficient: signature-less formats (notably CSV)
have no magic bytes, so anydoc.format_from_bytes() returns None for them.
anydoc.format_from_path() names the format from the path's extension; we use
bytes detection first, then fall back to the path when content is ambiguous.
"""

import anydoc

PDF_FORMAT = "pdf"


def detect_format(path) -> str:
    """Return the lowercase format name for the document at `path`
    (e.g. "pdf", "docx", "csv"), or "unknown" when undetectable."""
    try:
        path_str = str(path)
        with open(path_str, "rb") as f:
            data = f.read()
        fmt = anydoc.format_from_bytes(data)
        if fmt is not None:
            return str(fmt).lower()
        fmt = anydoc.format_from_path(path_str)
        if fmt is not None:
            return str(fmt).lower()
        return "unknown"
    except Exception:
        return "unknown"
