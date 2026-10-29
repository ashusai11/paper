"""
Agent 2 — Rebuild the ChromaDB index from SQLite
=================================================
ChromaDB is a derived search index. SQLite is the system of record. If the
ChromaDB directory is lost or corrupted, this tool recreates it from what
SQLite holds, without re-parsing any original file.

How it works
  documents.markdown and documents.json_blob (Agent 1's per-page output) are
  stored in SQLite. Chunking is deterministic, so re-chunking a stored document
  with the same TextChunker reproduces the same chunks: same text, same
  chunk IDs, same metadata (page number, native/OCR, OCR confidence, language).
  The chunks are re-embedded and upserted under those IDs, which makes the
  rebuild idempotent: running it twice changes nothing.

  The chunk logic below mirrors agent2_pass1() in main.py (JSON path first,
  markdown fallback). If you change chunking there, change it here too. The
  drift check exists to catch exactly that: every rebuilt chunk ID is compared
  with the IDs recorded in the SQLite `chunks` table at ingest time, and any
  difference is reported per document.

What this does NOT restore
  Pass 2 ("refinery") chunks: the structured certificate / NC / CTQ / identity
  chunks written after LLM extraction. Those come back by re-running Pass 2.
  Use --rerun-pass2 (needs LM Studio), or run agent2_pass2 per document.

Usage
    python rebuild_index.py --dry-run               # counts + drift report only
    python rebuild_index.py                         # rebuild everything
    python rebuild_index.py --supplier SUP-acme-...
    python rebuild_index.py --rerun-pass2
Requires the BGE-M3 embedder (FlagEmbedding) unless an embedder is injected.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))      # project root (config.py)

from chunker.text_chunker import TextChunker, stable_chunk_id     # noqa: E402
from storage.sqlite_store import SQLiteStore                      # noqa: E402


def _chunks_for_document(doc: dict, chunker: TextChunker) -> list[dict]:
    """Regenerate a stored document's ingestion chunks exactly as pass 1 built them."""
    supplier_id, document_id = doc["supplier_id"], doc["document_id"]
    chunks: list[dict] = []

    if doc.get("json_blob"):
        try:
            parsed = json.loads(doc["json_blob"]) if isinstance(doc["json_blob"], str) else doc["json_blob"]
            chunks = chunker.build_chunks_from_parsed(parsed, supplier_id, document_id)
        except Exception:
            chunks = []

    if not chunks:                                   # markdown fallback, as in pass 1
        raw = chunker.chunk(doc["markdown"], metadata={
            "source_file": Path(doc["file_name"]).name,
            "supplier_id": supplier_id,
            "supplier_name": doc.get("supplier_name") or "unknown",
            "document_id": document_id,
        })
        for c in raw:
            idx = c["metadata"].get("chunk_index", 0)
            ctype = c["metadata"].get("chunk_type", "general")
            chunks.append({"text": c["text"], "metadata": c["metadata"],
                           "id": stable_chunk_id(supplier_id, document_id, ctype, idx, c["text"])})
    return chunks


def _drift(regenerated: list[dict], stored_rows: list[dict]) -> Optional[dict]:
    """Compare regenerated chunk IDs with the IDs recorded in SQLite at ingest."""
    if not stored_rows:
        return None                     # nothing recorded (older ingest): cannot compare
    new_ids = {c["id"] for c in regenerated}
    old_ids = {r["chunk_id"] for r in stored_rows}
    if new_ids == old_ids:
        return None
    return {"stored_only": len(old_ids - new_ids), "regenerated_only": len(new_ids - old_ids)}


def rebuild_chroma_from_sqlite(
    sqlite_store: Optional[SQLiteStore] = None,
    chroma_store=None,
    embedder=None,
    supplier_id: Optional[str] = None,
    document_id: Optional[str] = None,
    batch_size: int = 32,
    dry_run: bool = False,
    rerun_pass2: bool = False,
    lm_studio_url: Optional[str] = None,
) -> dict:
    """
    Returns {"documents", "chunks_rebuilt", "chunks_failed", "no_stored_chunks",
             "drift": [{document_id, source_file, stored_only, regenerated_only}],
             "pass2": {"ok": n, "failed": n} (only with rerun_pass2)}.
    Stores and embedder are injectable (tests); defaults come from config.
    """
    if sqlite_store is None:
        sqlite_store = SQLiteStore()
        sqlite_store.initialize()

    sql = "SELECT * FROM documents"
    where, params = [], []
    if supplier_id:
        where.append("supplier_id = ?"); params.append(supplier_id)
    if document_id:
        where.append("document_id = ?"); params.append(document_id)
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY supplier_id, created_at"
    with sqlite_store.connect() as conn:
        documents = [dict(r) for r in conn.execute(sql, params).fetchall()]

    result: dict = {"documents": len(documents), "chunks_rebuilt": 0, "chunks_failed": 0,
                    "no_stored_chunks": 0, "drift": []}
    if not documents:
        return result

    if not dry_run:
        if chroma_store is None:
            from config import get_chroma_path
            from storage.chromadb_store import ChromaDBStore
            chroma_store = ChromaDBStore(persist_directory=str(get_chroma_path()))
            chroma_store.initialize()
        if embedder is None:
            from embeddings.bge_m3_embeddings import BGE_M3_Embeddings
            embedder = BGE_M3_Embeddings()

    chunker = TextChunker()
    for doc in documents:
        chunks = _chunks_for_document(doc, chunker)
        stored = sqlite_store.get_chunks(doc["document_id"])
        if not stored:
            result["no_stored_chunks"] += 1
        d = _drift(chunks, stored)
        if d:
            result["drift"].append({"document_id": doc["document_id"],
                                    "source_file": doc["file_name"], **d})

        if dry_run:
            result["chunks_rebuilt"] += len(chunks)
            continue
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            try:
                vectors = embedder.embed([c["text"] for c in batch])
                chroma_store.upsert_chunks(batch, vectors)
                result["chunks_rebuilt"] += len(batch)
            except Exception as e:
                result["chunks_failed"] += len(batch)
                print(f"  [rebuild] {doc['file_name']}: batch failed: {type(e).__name__}: {e}")

    if rerun_pass2 and not dry_run:
        result["pass2"] = _rerun_pass2(documents, sqlite_store, chroma_store, embedder, lm_studio_url)
    return result


def _rerun_pass2(documents, sqlite_store, chroma_store, embedder, lm_studio_url) -> dict:
    """Recreate the Pass 2 (refinery) chunks by running LLM refinement again per document."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("agent2_main", Path(__file__).resolve().parent / "main.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["agent2_main"] = mod
    spec.loader.exec_module(mod)
    ok = failed = 0
    for doc in documents:
        try:
            r = mod.agent2_pass2(document_id=doc["document_id"], supplier_id=doc["supplier_id"],
                                 sqlite_store=sqlite_store, chroma_store=chroma_store,
                                 embedder=embedder, lm_studio_url=lm_studio_url)
            if r.get("refined"):
                ok += 1
            else:
                failed += 1
                print(f"  [pass2] {doc['file_name']}: {r.get('status')}")
        except Exception as e:
            failed += 1
            print(f"  [pass2] {doc['file_name']}: {type(e).__name__}: {e}")
    return {"ok": ok, "failed": failed}


def _print(result: dict, dry_run: bool) -> None:
    print(f"\n=== ChromaDB rebuild ({'DRY RUN' if dry_run else 'DONE'}) ===")
    print(f"  Documents            : {result['documents']}")
    print(f"  Chunks {'to rebuild' if dry_run else 'rebuilt'}   : {result['chunks_rebuilt']}")
    if not dry_run:
        print(f"  Chunks failed        : {result['chunks_failed']}")
    if result["no_stored_chunks"]:
        print(f"  Documents with no rows in the SQLite chunks table (cannot cross-check): {result['no_stored_chunks']}")
    if result["drift"]:
        print("  DRIFT — regenerated chunk IDs differ from those recorded at ingest:")
        for d in result["drift"]:
            print(f"    {d['source_file']}: {d['stored_only']} recorded-only, {d['regenerated_only']} regenerated-only")
        print("    Cause: chunking code or settings changed since these documents were ingested.")
    else:
        print("  Drift check          : regenerated chunk IDs match the SQLite record")
    if "pass2" in result:
        print(f"  Pass 2 re-run        : {result['pass2']['ok']} ok, {result['pass2']['failed']} failed")
    elif not dry_run:
        print("  Note: Pass 2 (certificate / NC / CTQ) chunks are not restored; use --rerun-pass2.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Rebuild the ChromaDB index from SQLite")
    ap.add_argument("--supplier", default=None)
    ap.add_argument("--document", default=None)
    ap.add_argument("--batch-size", type=int, default=32)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rerun-pass2", action="store_true", help="also re-run LLM refinement (needs LM Studio)")
    ap.add_argument("--lm-studio-url", default=None)
    a = ap.parse_args()
    _print(rebuild_chroma_from_sqlite(supplier_id=a.supplier, document_id=a.document,
                                      batch_size=a.batch_size, dry_run=a.dry_run,
                                      rerun_pass2=a.rerun_pass2, lm_studio_url=a.lm_studio_url), a.dry_run)
