"""Orchestrator for the tabular (CSV / Excel) ingestion lane.

    sheet ──▶ route ──▶ map columns ──▶ refine (deterministic) ──▶ write rows
                                       │                            │
                                       └──▶ row chunks ──▶ embed ──┴──▶ ChromaDB

The same import writes to two places:

    Lane A (structured) the refined rows land in the SQLite table they were
    routed to (`purchase_history`, `company_profile`, …) with row-level
    provenance in `tabular_rows`.

    Lane B (RAG) the rows become text chunks (header repeated) that are
    embedded with BGE-M3 and upserted into ChromaDB, so a question about the
    spreadsheet is answered with a citation to file + sheet + row.

Both lanes share one `documents` row, so file-level dedup and versioning keep
working exactly as they do for PDF/DOCX.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any, Optional

from .reader import Sheet, TabularReadError, read_tabular
from .refine import map_columns, refine_sheet
from .registry import get_registry, get_target
from .router import make_llm_router, route_sheet
from .row_chunker import build_row_chunks
from .facts import project_facts
from .tabular_store import TabularStore

# ── bootstrap (same convention as api/main.py) ───────────────────────────────

def _bootstrap() -> None:
    here = Path(__file__).resolve().parent          # agent2_vectorstore/tabular
    agent2 = here.parent                            # agent2_vectorstore
    root = agent2.parent                            # pipeline root
    for p in (root, agent2):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))


_bootstrap()


def _make_store(db_path: Optional[Path] = None):
    """Build a store that is both the existing SQLiteStore and the tabular one."""
    from storage.sqlite_store import SQLiteStore

    class TabularSQLiteStore(TabularStore, SQLiteStore):
        pass

    store = TabularSQLiteStore(db_path) if db_path else TabularSQLiteStore()
    store.initialize()
    store.ensure_tabular_schema()
    return store


def _get_chroma_path() -> Path:
    try:
        import config  # type: ignore

        return config.get_chroma_path()
    except Exception:
        here = Path(__file__).resolve().parent.parent
        return here / "data" / "chroma"


def _file_hash(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _sheet_summary(sheets: list[Sheet]) -> str:
    """Compact JSON with one entry per sheet (the tabular equivalent of the
    per-page JSON the pipeline keeps for PDF/DOCX)."""
    payload = {
        "sheets": [
            {
                "name": s.name,
                "headers": s.headers,
                "row_count": s.row_count,
                "header_row": s.header_row,
                "preamble": s.preamble,
                "warnings": s.warnings,
            }
            for s in sheets
        ]
    }
    return json.dumps(payload, ensure_ascii=False)


def _file_markdown(sheets: list[Sheet], max_rows: int = 200) -> str:
    blocks = []
    for sheet in sheets:
        blocks.append(f"## Sheet: {sheet.name}\n\n{sheet.to_markdown(max_rows=max_rows)}")
    return "\n\n".join(blocks) + "\n"


# ── main entry point ─────────────────────────────────────────────────────────

def ingest_tabular(
    path: Path | str,
    supplier_id: Optional[str] = None,
    supplier_name: Optional[str] = None,
    target_table: Optional[str] = None,
    sheet_names: Optional[list[str]] = None,
    on_existing: Optional[str] = None,
    dry_run: bool = False,
    embed: bool = True,
    rows_per_chunk: int = 12,
    use_llm_routing: bool = False,
    registry: Optional[dict] = None,
    store=None,
    chroma_store=None,
    embedder=None,
) -> dict:
    """Ingest one CSV/Excel file.

    Returns a report dict:
        {
          "ok": bool,
          "file": "...", "format": "xlsx",
          "document_id": "...", "is_duplicate": False,
          "supplier_id": "SUP-...",
          "sheets": [
            {"name": "Orders", "target_table": "purchase_history",
             "route": {...}, "mapping": {...},
             "rows": {"total": 10, "inserted": 8, "updated": 1, "skipped": 1,
                      "failed": 0},
             "chunks_created": 2, "errors": [...]}
          ],
          "degraded": bool, "degraded_reason": str | None,
        }
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if not supplier_id:
        raise ValueError("supplier_id is required for tabular ingestion")

    registry = registry or get_registry()
    decimal_separator = registry.get("decimal_separator", "auto")
    dayfirst = bool(registry.get("dayfirst", True))

    # A dry run touches nothing: not even the database file. The store is
    # only created when there is something to write.
    store = store or (None if dry_run else _make_store())
    if store is not None:
        store.create_supplier(supplier_id, supplier_name)

    try:
        sheets = read_tabular(path)
    except TabularReadError as exc:
        return {
            "ok": False, "file": path.name, "supplier_id": supplier_id,
            "error": str(exc), "degraded": True, "degraded_reason": str(exc),
            "sheets": [],
        }

    if sheet_names:
        wanted = {s.lower() for s in sheet_names}
        sheets = [s for s in sheets if s.name.lower() in wanted]
    if not sheets:
        return {
            "ok": False, "file": path.name, "supplier_id": supplier_id,
            "error": "no sheet selected / no readable sheet", "sheets": [],
        }

    source_format = sheets[0].source_format
    file_hash = _file_hash(path)
    markdown = _file_markdown(sheets)

    # ── one document row per file (dedup + versioning, like PDF/DOCX) ────────
    if dry_run or store is None:
        document_id, is_new = None, True
    else:
        document_id, is_new = store.store_document(
            supplier_id=supplier_id,
            file_path=path,
            markdown=markdown,
            json_blob=_sheet_summary(sheets),
            page_count=len(sheets),
            doc_format=source_format,
            supplier_name=supplier_name,
        )

    llm_router = make_llm_router() if use_llm_routing else None
    sheet_reports: list[dict] = []
    degraded_reason: Optional[str] = None
    total_chunks = 0

    try:
        for sheet in sheets:
            route = route_sheet(sheet, path.name, registry,
                                target_override=target_table, llm_router=llm_router)
            tdef = get_target(registry, route["target"])
            mapping_info = map_columns(sheet.headers, tdef)

            records, errors = refine_sheet(
                sheet, tdef, mapping_info,
                decimal_separator=decimal_separator, dayfirst=dayfirst,
            )

            # A master sheet that lists MANY suppliers must not be written into
            # `company_profile` (that would overwrite the profile of the supplier
            # under review). Such sheets are redirected to `supplier_directory`.
            if tdef.get("kind") == "supplier_profile":
                identities = {
                    r["record"].get("legal_name") for r in records
                    if r["record"].get("legal_name")
                }
                if len(identities) > 1:
                    directory_def = get_target(registry, "supplier_directory")
                    route = {
                        **route,
                        "target": "supplier_directory",
                        "table": directory_def.get("table", "supplier_directory"),
                        "kind": directory_def.get("kind", "supplier_directory"),
                        "method": f"{route.get('method')}+multi_supplier",
                        "reason": (f"sheet lists {len(identities)} suppliers — "
                                   "written to supplier_directory instead of "
                                   "company_profile"),
                    }
                    tdef = directory_def
                    mapping_info = map_columns(sheet.headers, tdef)
                    records, errors = refine_sheet(
                        sheet, tdef, mapping_info,
                        decimal_separator=decimal_separator, dayfirst=dayfirst,
                    )

            import_id = "dry-run" if (dry_run or store is None) else store.start_import(
                supplier_id=supplier_id,
                source_file=path.name,
                sheet_name=sheet.name,
                target_table=route["table"] or "tabular_records",
                source_format=source_format,
                file_hash=file_hash,
                file_path=str(path),
                mapping=mapping_info,
                route=route,
                needs_review=route.get("needs_review", False),
            )

            # The head of the sheet is stored once — the ordered column names —
            # so the raw rows below always have a header to belong to.
            sheet_id = ("dry-run" if (dry_run or store is None) else store.store_sheet(
                import_id=import_id, supplier_id=supplier_id, source_file=path.name,
                sheet_name=sheet.name, headers=sheet.headers, row_count=len(sheet.rows),
                source_format=source_format, preamble=sheet.preamble,
            ))

            counts = {"total": len(records), "inserted": 0, "updated": 0,
                      "skipped": 0, "failed": 0}
            if dry_run:
                # A dry run reports what WOULD happen — it must never look
                # like rows were written.
                counts["planned"] = 0
            policy = on_existing or tdef.get("on_existing", "update")
            written_payloads: list[dict] = []
            fact_rows: list[dict] = []
            row_supplier_ids: dict[int, str] = {}
            row_supplier_names: dict[int, str] = {}

            # ERP exports list many vendors: every row is attributed to the
            # supplier named in `row_supplier_field`, not to the supplier the
            # file was uploaded for.
            row_supplier_field = tdef.get("row_supplier_field")
            table_columns = [
                fname for fname, fdef in (tdef.get("fields") or {}).items()
                if fdef.get("table_column", True)
            ]
            # The fields that identify a row. Defaults to the natural key, but a
            # target may widen it (e.g. reference + date) when an ERP reuses
            # order numbers — then two orders with one number stay two orders.
            match_fields = tdef.get("match_fields") or tdef.get("natural_key") or []

            for index, item in enumerate(records):
                source_row = item["source_row"]
                record = item["record"]
                payload = {**record}
                if item["extra"]:
                    payload["_extra"] = item["extra"]

                # resolve the supplier this row belongs to (before the error
                # check, so even a rejected raw row knows its company)
                row_supplier_id = supplier_id
                row_supplier_name = supplier_name or ""
                if row_supplier_field:
                    candidate = (record.get(row_supplier_field) or "").strip()
                    if not candidate:
                        raw_row = sheet.rows[index] if index < len(sheet.rows) else {}
                        candidate = str(raw_row.get(row_supplier_field) or "").strip()
                    if candidate:
                        if dry_run:
                            row_supplier_id = f"(would resolve: {candidate})"
                            row_supplier_name = candidate
                        else:
                            row_supplier_id, row_supplier_name = store.resolve_supplier_id(
                                candidate, context_supplier_id=supplier_id)
                row_supplier_ids[index] = row_supplier_id
                row_supplier_names[index] = row_supplier_name

                # the raw row, verbatim, with the original headers as keys —
                # written for EVERY row, including the ones we later reject
                if not dry_run:
                    raw_row = sheet.rows[index] if index < len(sheet.rows) else {}
                    store.store_raw_row(
                        import_id=import_id, sheet_id=sheet_id,
                        supplier_id=row_supplier_id, source_file=path.name,
                        sheet_name=sheet.name, source_row=source_row,
                        raw_row={h: raw_row.get(h) for h in sheet.headers},
                    )

                if item["errors"]:
                    counts["failed"] += 1
                    if store is not None:
                        for err in item["errors"]:
                            store.record_error(import_id, sheet.name, source_row,
                                               err["column"], err["message"],
                                               err.get("raw_value"))
                    continue

                row_hash = TabularStore.row_hash(payload)
                action = "inserted"
                target_table_name = route["table"] or "tabular_records"
                match_key = "|".join(
                    str(record.get(f, "")) for f in match_fields
                ).strip("|")
                natural_key = match_key or item["natural_key"] or row_hash

                if not dry_run:
                    kind = tdef.get("kind", "raw_records")
                    unchanged = (
                        bool(natural_key)
                        and store.last_row_hash(row_supplier_id, target_table_name, natural_key)
                        == row_hash
                    )
                    if unchanged:
                        # identical content already imported -> idempotent no-op
                        action = "skipped"
                    elif kind == "purchase_history":
                        action, _prev = store.upsert_purchase(
                            row_supplier_id, record, on_existing=policy,
                            columns=table_columns, match_fields=match_fields)
                    elif kind == "supplier_profile":
                        store.upsert_company_profile(supplier_id, record)
                        action = "inserted"
                    elif kind == "supplier_directory":
                        action = store.upsert_supplier_directory(
                            supplier_id, record, import_id=import_id,
                            source_file=path.name, sheet_name=sheet.name,
                            source_row=source_row, row_hash=row_hash,
                        )
                    elif kind == "generic":
                        # Any registry-defined target: the table is created from
                        # the registry on first import, then upserted like any
                        # other target. A new kind of spreadsheet is a JSON
                        # entry, not a Python class.
                        action, _prev = store.upsert_generic_table(
                            row_supplier_id, tdef, record, match_fields=match_fields,
                            on_existing=policy, columns=table_columns,
                        )
                    else:
                        store.insert_raw_record(
                            supplier_id, import_id, path.name, sheet.name,
                            source_row, payload)
                        action = "inserted"

                    store.record_row(
                        import_id=import_id, supplier_id=row_supplier_id,
                        target_table=target_table_name,
                        natural_key=natural_key,
                        source_file=path.name, sheet_name=sheet.name,
                        source_row=source_row, payload=payload, action=action,
                        row_hash=row_hash, document_id=document_id,
                    )

                if dry_run:
                    counts["planned"] = counts.get("planned", 0) + 1
                else:
                    counts[action] = counts.get(action, 0) + 1
                if action == "error":
                    counts["failed"] += 1
                    counts["error"] = counts.get("error", 0) + 1
                written_payloads.append(payload)

                # Rows that were written may imply facts about the supplier
                # (a certificate, an NC, a risk). Which facts a sheet implies
                # is declared per target in the registry — purchase history
                # declares none, because the orders themselves are the
                # evidence the economic evaluation already reads.
                fact_rows.append({
                    "record": record,
                    "raw_row": sheet.rows[index] if index < len(sheet.rows) else {},
                    "source_row": source_row,
                    "supplier_id": row_supplier_id,
                })

            # ── Lane B: RAG chunks ───────────────────────────────────────────────
            chunks_created = 0
            # Defined here, not inside the embed branch: the fact projection
            # below reads the chunk ids even when indexing is switched off.
            all_chunks: list[dict] = []
            if embed and not dry_run:
                # One chunk group per supplier: a chunk must belong to exactly one
                # supplier, otherwise the ChromaDB supplier filter breaks.
                groups: dict[str, list[int]] = {}
                for index in range(len(records)):
                    sid = row_supplier_ids.get(index, supplier_id)
                    groups.setdefault(sid, []).append(index)

                for sid, indexes in groups.items():
                    base_meta = {
                        "source_file": path.name,
                        "source_format": source_format,
                        "sheet_name": sheet.name,
                        "target_table": route["table"] or "tabular_records",
                        "supplier_id": sid,
                        "supplier_name": row_supplier_names.get(
                            indexes[0], supplier_name or "unknown"),
                        "document_id": document_id,
                        "doc_type": "tabular",
                        "document_type": "tabular",
                    }
                    all_chunks.extend(build_row_chunks(
                        sheet,
                        [sheet.rows[i] for i in indexes],
                        [sheet.row_numbers[i] for i in indexes],
                        base_meta,
                        rows_per_chunk=rows_per_chunk,
                    ))

                # chunk_index must stay unique across the whole file
                for position, chunk in enumerate(all_chunks):
                    chunk["metadata"]["chunk_index"] = position

                chunks = all_chunks
                if chunks:
                    try:
                        if embedder is None:
                            from embeddings.bge_m3_embeddings import BGE_M3_Embeddings

                            embedder = BGE_M3_Embeddings()
                        if chroma_store is None:
                            from storage.chromadb_store import ChromaDBStore

                            chroma_store = ChromaDBStore(
                                persist_directory=str(_get_chroma_path()))
                            chroma_store.initialize()
                        embeddings = embedder.embed([c["text"] for c in chunks])
                        chroma_store.upsert_chunks(chunks, embeddings)
                        for c in chunks:
                            try:
                                store.store_chunk(
                                    document_id=document_id,
                                    chunk_id=c["id"],
                                    chunk_index=c["metadata"].get("chunk_index", 0),
                                    text=c["text"],
                                )
                            except Exception:
                                pass
                        chunks_created = len(chunks)
                        total_chunks += chunks_created
                    except Exception as exc:  # degrade, never crash the import
                        degraded_reason = f"embedding/indexing unavailable: {exc}"

            # ── Lane C: facts ───────────────────────────────────────────────────
            # A certificate register in a spreadsheet must reach the same
            # `profile_facts` the PDF lane fills, otherwise the certification
            # criterion sees an empty supplier. The projection is deterministic
            # (no model) and carries its provenance.
            facts_written = 0
            if fact_rows and not dry_run and store is not None:
                chunk_lookup: dict[int, str] = {}
                for chunk in all_chunks:
                    meta = chunk.get("metadata", {})
                    start, end = meta.get("row_start"), meta.get("row_end")
                    if start is None:
                        continue
                    for row_no in range(int(start), int(end) + 1):
                        chunk_lookup[row_no] = chunk["id"]
                try:
                    facts_written = project_facts(
                        store, tdef, fact_rows,
                        document_id=document_id,
                        chunk_lookup=chunk_lookup,
                        sheet_name=sheet.name,
                    )
                except Exception as exc:  # never fail an import over facts
                    degraded_reason = (degraded_reason or "") + (
                        f"; fact projection failed: {exc}"
                    ).strip("; ")

            if not dry_run:
                store.finish_import(
                    import_id,
                    status="completed_with_errors" if counts["failed"] else "completed",
                    counts=counts,
                )

            sheet_reports.append({
                "name": sheet.name,
                "target_table": route["table"],
                "target": route["target"],
                "route": route,
                "mapping": mapping_info,
                "rows": counts,
                "facts_written": facts_written,
                "chunks_created": chunks_created,
                "import_id": import_id,
                "errors": errors[:50],
                "warnings": sheet.warnings,
            })

    except Exception as exc:
        # A crashed import must leave an audit record, not a row that
        # looks like it is still running.
        message = f"{type(exc).__name__}: {exc}"
        if store is not None:
            store.fail_running_imports(supplier_id, path.name, message)
        for report in sheet_reports:
            report.setdefault("status", "completed")
        sheet_reports.append({
            "name": None, "target_table": None, "target": None,
            "status": "failed", "error": message,
            "route": {}, "mapping": {"mapping": {}, "unmapped": []},
            "rows": {"total": 0, "inserted": 0, "updated": 0,
                     "skipped": 0, "failed": 0},
            "chunks_created": 0, "errors": [], "warnings": [],
        })
        return {
            "ok": False, "file": path.name, "file_path": str(path),
            "format": source_format, "supplier_id": supplier_id,
            "document_id": document_id, "is_duplicate": not is_new,
            "dry_run": dry_run, "sheets": sheet_reports,
            "chunks_created": total_chunks,
            "degraded": True, "degraded_reason": message,
            "error": message,
        }
    return {
        "ok": True,
        "file": path.name,
        "file_path": str(path),
        "format": source_format,
        "supplier_id": supplier_id,
        "document_id": document_id,
        "is_duplicate": not is_new,
        "dry_run": dry_run,
        "sheets": sheet_reports,
        "chunks_created": total_chunks,
        "degraded": bool(degraded_reason),
        "degraded_reason": degraded_reason,
    }


def ingest_tabular_directory(
    directory: Path | str,
    supplier_id: Optional[str] = None,
    supplier_name: Optional[str] = None,
    **kwargs,
) -> dict:
    """Ingest every CSV/XLSX/XLS file in a directory."""
    directory = Path(directory)
    files = sorted(
        p for p in directory.iterdir()
        if p.suffix.lower() in (".csv", ".tsv", ".txt", ".xlsx", ".xlsm")
    )
    results = []
    for file in files:
        try:
            results.append(ingest_tabular(file, supplier_id=supplier_id,
                                          supplier_name=supplier_name, **kwargs))
        except Exception as exc:
            results.append({"ok": False, "file": file.name, "error": str(exc)})
    return {
        "ok": all(r.get("ok") for r in results),
        "files": len(results),
        "results": results,
    }
