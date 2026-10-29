"""Row-window chunking for the RAG lane.

A spreadsheet row is only meaningful *with its header* — "1250,00" is nothing
without knowing it is the `amount` column. So every chunk repeats the header
line and then carries a window of rows:

    File: buy_history_2024.xlsx | Sheet: Orders | Table: purchase_history
    Columns: Purchase Date | PO Number | Product | Amount | Currency

    Row 2: Purchase Date=2024-01-05 | PO Number=PO-1001 | Product=Valve | ...
    Row 3: ...

Metadata keeps the citation precise: `sheet_name`, `row_start`, `row_end`,
`target_table`, `source_file`. Chroma metadata values must be scalars, so
`None` is normalised to `""` before upsert.
"""

from __future__ import annotations

import hashlib
from typing import Any, Optional

DEFAULT_ROWS_PER_CHUNK = 12
MAX_CELLS_PER_ROW = 14


def _clean(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value != value:
        return ""
    s = str(value).strip()
    return " ".join(s.split())


def _row_line(number: int, row: dict, headers: list[str],
              max_cells: int) -> str:
    cells = []
    for h in headers[:max_cells]:
        v = _clean(row.get(h))
        cells.append(f"{h}={v}" if v else f"{h}=")
    extra = len(headers) - max_cells
    if extra > 0:
        cells.append(f"(+{extra} more columns)")
    return f"Row {number}: " + " | ".join(cells)


def build_row_chunks(
    sheet,
    rows: list[dict],
    row_numbers: list[int],
    base_metadata: Optional[dict] = None,
    rows_per_chunk: int = DEFAULT_ROWS_PER_CHUNK,
    max_cells: int = MAX_CELLS_PER_ROW,
) -> list[dict]:
    """Build RAG chunks from a sheet's rows.

    Returns a list of `{"id", "text", "metadata"}` dicts ready for
    `ChromaDBStore.upsert_chunks` and `SQLiteStore.store_chunk`.
    """
    if not rows:
        return []

    base = dict(base_metadata or {})
    headers = list(sheet.headers)
    header_line = " | ".join(headers)

    chunks: list[dict] = []
    for chunk_index, start in enumerate(range(0, len(rows), rows_per_chunk)):
        window = rows[start:start + rows_per_chunk]
        numbers = row_numbers[start:start + rows_per_chunk]
        if not window:
            continue

        body = "\n".join(
            _row_line(n, r, headers, max_cells) for n, r in zip(numbers, window)
        )
        text = (
            f"File: {base.get('source_file', 'unknown')} | "
            f"Sheet: {base.get('sheet_name', sheet.name)} | "
            f"Table: {base.get('target_table', 'unknown')}\n"
            f"Columns: {header_line}\n\n"
            f"{body}"
        )

        metadata = {
            **base,
            "chunk_index": chunk_index,
            "chunk_type": "tabular",
            "row_start": numbers[0],
            "row_end": numbers[-1],
            "row_count": len(window),
            "section": f"{base.get('sheet_name', sheet.name)} rows {numbers[0]}-{numbers[-1]}",
            "contains_risk": "false",
            "risk_severity": "none",
            "language": base.get("language", "de"),
            "chunk_hash": hashlib.sha256(text.encode("utf-8")).hexdigest()[:16],
        }
        chunks.append({
            "id": _chunk_id(base, chunk_index, text),
            "text": text,
            "metadata": sanitize_metadata(metadata),
        })
    return chunks


def _chunk_id(base: dict, index: int, text: str) -> str:
    """Stable, deterministic id — same file + same content = same id."""
    from hashlib import sha256

    raw = "|".join([
        str(base.get("supplier_id", "")),
        str(base.get("document_id", "")),
        str(base.get("sheet_name", "")),
        str(index),
        text,
    ])
    return sha256(raw.encode("utf-8")).hexdigest()[:32]


def sanitize_metadata(metadata: dict) -> dict:
    """ChromaDB accepts only scalar metadata (str/int/float/bool)."""
    out: dict[str, Any] = {}
    for key, value in (metadata or {}).items():
        if value is None:
            out[key] = ""
        elif isinstance(value, (str, int, float, bool)):
            out[key] = value
        else:
            out[key] = str(value)
    return out
