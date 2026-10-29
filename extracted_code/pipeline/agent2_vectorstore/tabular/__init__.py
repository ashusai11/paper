"""Tabular ingestion lane (CSV / XLSX / XLS) for the supplier pipeline.

Design in one paragraph:
    A spreadsheet is NOT a document. Running `anydoc` over it flattens the grid
    into markdown and destroys the row/column semantics you need to write into
    `purchase_history` (or any other "respected table"). So tabular files get
    their own two-lane path:

        Lane A (STRUCTURED)  sheet -> route to target table -> column mapping
                             -> deterministic normalization/validation -> upsert
                             into the target SQLite table (with row provenance)

        Lane B (RAG)         the same rows re-serialized as text with the header
                             repeated, chunked per row-window, embedded (BGE-M3)
                             and upserted into ChromaDB, so a question like
                             "which orders of Acme were late?" is answered with a
                             citation that points at file + sheet + row.

    The two lanes share one document row, so `documents.document_hash` still
    gives you file-level dedup and versioning.

Modules:
    reader.py       robust CSV/XLSX reading (encoding, delimiter, header row,
                    multi-sheet, merged headers)
    registry.py     table registry: target tables, field aliases, routing rules
    router.py       sheet -> target table resolution (rules -> header score ->
                    optional LLM fallback -> safe default)
    refine.py       deterministic normalization + validation + column mapping
    row_chunker.py  row-window chunks with repeated header (Lane B)
    tabular_store.py  extra SQLite tables: tabular_imports / tabular_rows /
                    tabular_errors
    ingest.py       orchestrator (stage -> route -> refine -> write -> index)
    cli.py          `python -m agent2_vectorstore.tabular.cli --file ...`
"""

from .ingest import ingest_tabular, ingest_tabular_directory  # noqa: F401
from .reader import Sheet, read_tabular  # noqa: F401
from .registry import get_registry, get_registry_path  # noqa: F401
from .router import route_sheet  # noqa: F401

__all__ = [
    "ingest_tabular",
    "ingest_tabular_directory",
    "Sheet",
    "read_tabular",
    "get_registry",
    "get_registry_path",
    "route_sheet",
]
