"""API routes for tabular (CSV / Excel) ingestion.

Include in `api/main.py` (one line, after the app is created):

    from api.tabular_routes import router as tabular_router
    app.include_router(tabular_router)

Routes:
    POST /ingest/tabular   upload a CSV/XLSX -> rows into the target table +
                            row-window chunks into ChromaDB
    GET  /tabular/targets  the registered target tables and their fields
    GET  /tabular/imports  import history (what was routed where, row counts)
    GET  /tabular/imports/{import_id}  one import incl. its row errors
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

_ROOT = Path(__file__).resolve().parent.parent
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

router = APIRouter(prefix="/tabular", tags=["tabular"])

ALLOWED_SUFFIXES = {".csv", ".tsv", ".txt", ".xlsx", ".xlsm"}


class TabularIngestResponse(BaseModel):
    ok: bool
    file: str
    format: Optional[str] = None
    supplier_id: Optional[str] = None
    document_id: Optional[str] = None
    is_duplicate: bool = False
    dry_run: bool = False
    chunks_created: int = 0
    degraded: bool = False
    degraded_reason: Optional[str] = None
    error: Optional[str] = None
    sheets: list[dict] = []


@router.post("/ingest", response_model=TabularIngestResponse)
async def ingest_tabular(
    file: UploadFile = File(...),
    supplier_id: Optional[str] = Form(None),
    supplier_name: Optional[str] = Form(None),
    target_table: Optional[str] = Form(None),
    sheet: Optional[str] = Form(None),
    on_existing: Optional[str] = Form(None),
    dry_run: bool = Form(False),
    embed: bool = Form(True),
):
    """Ingest a CSV/Excel file into the target table and the vector index."""
    if not supplier_id and not (supplier_name and supplier_name.strip()):
        raise HTTPException(400, "supplier_id or supplier_name is required")

    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            400,
            f"unsupported file type '{suffix or '?'}' — "
            f"allowed: {', '.join(sorted(ALLOWED_SUFFIXES))}",
        )

    from agent2_vectorstore.tabular.ingest import ingest_tabular as _ingest

    content = await file.read()
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        report = _ingest(
            tmp_path,
            supplier_id=supplier_id,
            supplier_name=supplier_name,
            target_table=target_table,
            sheet_names=[sheet] if sheet else None,
            on_existing=on_existing,
            dry_run=dry_run,
            embed=embed,
        )
    finally:
        tmp_path.unlink(missing_ok=True)

    if not report.get("ok"):
        raise HTTPException(400, report.get("error", "tabular ingestion failed"))

    return TabularIngestResponse(
        ok=True,
        file=report.get("file", ""),
        format=report.get("format"),
        supplier_id=report.get("supplier_id"),
        document_id=report.get("document_id"),
        is_duplicate=bool(report.get("is_duplicate")),
        dry_run=bool(report.get("dry_run")),
        chunks_created=int(report.get("chunks_created", 0)),
        degraded=bool(report.get("degraded")),
        degraded_reason=report.get("degraded_reason"),
        sheets=report.get("sheets", []),
    )


@router.get("/targets")
def list_targets():
    """The registered target tables (editable in table_registry.json)."""
    from agent2_vectorstore.tabular.registry import get_registry, get_registry_path, list_targets as _list

    registry = get_registry()
    return {
        "registry_path": str(get_registry_path()),
        "targets": _list(registry),
        "routes": registry.get("routes", []),
    }


@router.get("/imports")
def list_imports(supplier_id: Optional[str] = None, limit: int = 50):
    """Import history: what was routed where, and how many rows landed."""
    from agent2_vectorstore.tabular.ingest import _make_store

    store = _make_store()
    return {"imports": store.list_imports(supplier_id=supplier_id, limit=limit)}


@router.get("/imports/{import_id}")
def get_import(import_id: str):
    """One import with its row-level provenance and validation errors."""
    from agent2_vectorstore.tabular.ingest import _make_store

    store = _make_store()
    imp = store.get_import(import_id)
    if not imp:
        raise HTTPException(404, "import not found")
    return {
        "import": imp,
        "rows": store.list_rows(import_id),
        "errors": store.list_errors(import_id),
        "sheets": store.get_sheet(import_id),
    }


@router.get("/raw")
def list_raw_rows(
    import_id: Optional[str] = None,
    supplier_id: Optional[str] = None,
    sheet_name: Optional[str] = None,
    vendor: Optional[str] = None,
    limit: int = 500,
):
    """The raw grid, row by row.

    Every row is stored verbatim with the ORIGINAL column names as keys, so
    a row explains itself: you always know which company it belongs to and
    what every cell means. `vendor` filters on a column value, e.g.
    `?vendor=Vendor&value=Amazon EU SARL`.
    """
    from agent2_vectorstore.tabular.ingest import _make_store

    store = _make_store()
    rows = store.list_raw_rows(import_id=import_id, supplier_id=supplier_id,
                                sheet_name=sheet_name, limit=limit)
    if vendor:
        key = vendor
        rows = [r for r in rows if r["row"].get(key) is not None]
    return {"count": len(rows), "rows": rows}
