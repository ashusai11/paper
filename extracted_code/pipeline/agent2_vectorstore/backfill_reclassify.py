"""
Agent 2 — Backfill Reclassification
====================================
Re-label documents that were stored before the classifier changed.

Why this exists
  The classifier runs once, at ingest. Documents stored before the
  "quality_agreement" rule was added keep the label they got then (usually
  "other" or "quality_report"). This script re-runs the CURRENT classifier on
  the stored markdown and updates refined_data.doc_type where it differs.

What it changes
  Only doc_type. Extracted certificates, dates, nonconformances and profile
  facts are left exactly as they are. A document with no refined_data row gets
  a skeleton row (marked degraded: nothing has been extracted from it yet).

Safe to re-run: idempotent, and --dry-run previews without writing.

Database path: by default SQLiteStore() uses config.get_db_path(), the same
file every other component uses. (The previous version defaulted to the
relative path "data/supplier_risk.db", which points at a different database
depending on the directory you run it from.)

Usage (from agent2_vectorstore/ or anywhere):
    python backfill_reclassify.py --dry-run
    python backfill_reclassify.py
    python backfill_reclassify.py --supplier SUP-acme-a1b2c3d4
    python backfill_reclassify.py --db /explicit/path/supplier_risk.db
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from refinery.classifier import classify_document      # noqa: E402
from storage.sqlite_store import SQLiteStore            # noqa: E402


def _open_store(db_path: str | None) -> SQLiteStore:
    store = SQLiteStore(db_path) if db_path else SQLiteStore()
    store.initialize()          # idempotent: makes sure newer columns exist
    return store


def _fetch_documents(store: SQLiteStore, supplier_id: str | None) -> list[dict]:
    sql = "SELECT document_id, supplier_id, file_name, markdown FROM documents"
    params: tuple = ()
    if supplier_id:
        sql += " WHERE supplier_id = ?"
        params = (supplier_id,)
    with store.connect() as conn:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]


def run_backfill(db_path: str | None = None, supplier_id: str | None = None,
                 dry_run: bool = False, store: SQLiteStore | None = None) -> dict:
    """
    Returns {"scanned", "changed", "unchanged", "no_refined_row", "transitions": [...]}.
    Each transition: document_id, source_file, supplier_id, old_doc_type, new_doc_type.
    """
    store = store or _open_store(db_path)
    documents = _fetch_documents(store, supplier_id)

    changed = unchanged = no_refined_row = 0
    transitions: list[dict] = []

    for doc in documents:
        new_type = classify_document(doc["markdown"])
        rows = store.get_refined_data(doc["supplier_id"], doc["document_id"])
        base = {"document_id": doc["document_id"], "source_file": doc["file_name"],
                "supplier_id": doc["supplier_id"], "new_doc_type": new_type}

        if not rows:
            no_refined_row += 1
            transitions.append({**base, "old_doc_type": None,
                                "note": "no existing refined_data row"})
        else:
            old_type = rows[0].get("doc_type")
            if old_type == new_type:
                unchanged += 1
                continue
            changed += 1
            transitions.append({**base, "old_doc_type": old_type})

        if not dry_run:
            store.upsert_refined_data(
                supplier_id=doc["supplier_id"], document_id=doc["document_id"],
                source_file=doc["file_name"], doc_type=new_type)

    return {"scanned": len(documents), "changed": changed, "unchanged": unchanged,
            "no_refined_row": no_refined_row, "transitions": transitions}


def _print_summary(result: dict, dry_run: bool) -> None:
    print(f"\n=== Backfill reclassification ({'DRY RUN — nothing written' if dry_run else 'APPLIED'}) ===")
    print(f"  Documents scanned   : {result['scanned']}")
    print(f"  Reclassified        : {result['changed']}")
    print(f"  Unchanged           : {result['unchanged']}")
    print(f"  No refined_data row : {result['no_refined_row']}")
    for t in result["transitions"]:
        flag = "  <- QAA detected" if t["new_doc_type"] == "quality_agreement" else ""
        print(f"    [{t['supplier_id']}] {t['source_file']}: {t['old_doc_type']} -> {t['new_doc_type']}{flag}")
    if not result["transitions"]:
        print("  Nothing to change: every document already has the current label.")
    if dry_run and result["transitions"]:
        print("\n  Run again without --dry-run to apply.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Re-label stored documents with the current classifier")
    ap.add_argument("--db", default=None, help="SQLite path (default: config.get_db_path())")
    ap.add_argument("--supplier", default=None, help="Limit to one supplier_id")
    ap.add_argument("--dry-run", action="store_true", help="Preview only")
    a = ap.parse_args()
    _print_summary(run_backfill(a.db, a.supplier, a.dry_run), a.dry_run)
