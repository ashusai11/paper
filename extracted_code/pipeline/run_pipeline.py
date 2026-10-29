"""
run_pipeline.py — Ingest documents from the command line
=========================================================
  document(s) on disk
      → Agent 1  parse (offline, no LLM)
      → Agent 2  pass 1: dedup, store in SQLite, chunk, embed, index in ChromaDB
      → Agent 2  pass 2: LLM extraction of certificates, dates, NCs … (LM Studio)

Evaluating a supplier is NOT done here. The evaluation asks a person questions
(risk-classification answers, QAA / audit status, economic scores) and ends with
a human decision, so it runs in the web UI / API. When ingestion finishes this
script tells you what to open next.

The API's /ingest route does the same work for one uploaded file. Use this
script for batches (a folder of documents) or when the API is not running.

Usage
    python run_pipeline.py cert.pdf --supplier-name "Acme Medizintechnik GmbH"
    python run_pipeline.py ./acme_docs/ --supplier-id SUP-acme-001
    python run_pipeline.py a.pdf b.docx --supplier-name "Acme" --skip-pass2
    python run_pipeline.py ./acme_docs/ --supplier-name "Acme" --lm-studio-url http://192.168.1.50:1234

Supplier identity
  Pass --supplier-id (your own stable ID) or --supplier-name (a stable ID is
  derived from the name: same name → same ID, no date in it). One of them is
  required: Agent 2's own generate_supplier_id() includes today's date, so the
  same supplier would get a different ID every day and its documents would
  never be grouped together.

Paths come from config.py (database, ChromaDB, parsed output), the same files
the API and UI use. LM Studio's address comes from LM_STUDIO_URL / .env.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Optional

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

SUPPORTED = {".pdf", ".docx"}


def stable_supplier_id(name: str) -> str:
    """Same name → same ID, every time (case and surrounding spaces ignored)."""
    digest = hashlib.sha1(name.strip().lower().encode()).hexdigest()[:8]
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:32] or "supplier"
    return f"SUP-{slug}-{digest}"


def collect_files(paths: list[str]) -> list[Path]:
    """Files given directly, plus supported files directly inside given folders (sorted)."""
    found: list[Path] = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            found += sorted(f for f in p.iterdir() if f.is_file() and f.suffix.lower() in SUPPORTED)
        elif p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"Not found: {raw}")
    return found


class _Agents:
    """The real Agent 1 / Agent 2 entry points and shared stores. Loaded lazily."""

    def __init__(self) -> None:
        try:
            import agent1_offline.main as agent1
            spec = importlib.util.spec_from_file_location(
                "agent2_main", _ROOT / "agent2_vectorstore" / "main.py")
            agent2 = importlib.util.module_from_spec(spec)
            sys.modules["agent2_main"] = agent2      # both agents have a main.py: load by path
            spec.loader.exec_module(agent2)
            from config import get_chroma_path, get_data_dir
            from embeddings.bge_m3_embeddings import BGE_M3_Embeddings
            from storage.chromadb_store import ChromaDBStore
            from storage.sqlite_store import SQLiteStore
        except ImportError as e:
            raise SystemExit(f"Missing dependency: {e}\nInstall with: pip install -r requirements.txt")

        self.parse_document = agent1.parse_document
        self.pass1, self.pass2 = agent2.agent2_pass1, agent2.agent2_pass2
        self.out_dir = get_data_dir() / "parsed_documents"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.sqlite = SQLiteStore()
        self.sqlite.initialize()
        self.chroma = ChromaDBStore(persist_directory=str(get_chroma_path()))
        self.chroma.initialize()
        print("Loading the BGE-M3 embedding model (first run downloads ~2.2 GB)...")
        self.embedder = BGE_M3_Embeddings()


def ingest_file(path: Path, supplier_id: str, supplier_name: Optional[str],
                agents, skip_pass2: bool, lm_studio_url: Optional[str]) -> dict:
    """Run one file through the pipeline. Returns a summary row; never raises."""
    row = {"file": path.name, "status": "ok", "document_id": None, "doc_type": None,
           "chunks": 0, "pass2": "skipped" if skip_pass2 else "-", "note": ""}
    try:
        parsed = agents.parse_document(str(path), output_dir=str(agents.out_dir))
        p1 = agents.pass1(
            markdown=parsed["full_markdown"], file_path=path,
            supplier_id=supplier_id, supplier_name=supplier_name,
            sqlite_store=agents.sqlite, chroma_store=agents.chroma, embedder=agents.embedder,
            # The per-page JSON gives page-level chunks with page numbers and OCR
            # metadata. Without it pass 1 falls back to plain markdown chunking.
            json_blob=json.dumps(parsed, default=str),
            page_count=parsed.get("page_count"), doc_format=parsed.get("format"))
        row.update(document_id=p1["document_id"], chunks=p1.get("chunks_created", 0))

        if p1.get("is_duplicate"):
            row.update(status="duplicate", pass2="skipped",
                       note="identical content already stored")
        elif not skip_pass2:
            p2 = agents.pass2(document_id=p1["document_id"], supplier_id=supplier_id,
                              sqlite_store=agents.sqlite, chroma_store=agents.chroma,
                              embedder=agents.embedder, lm_studio_url=lm_studio_url)
            row["doc_type"] = p2.get("doc_type")
            if p2.get("refined"):
                row["pass2"] = "ok"
            else:
                row["pass2"] = "degraded"
                row["note"] = str(p2.get("status") or "")
    except Exception as e:
        row.update(status="FAILED", note=f"{type(e).__name__}: {e}")
    return row


def run_ingest(paths: list[str], supplier_id: Optional[str], supplier_name: Optional[str],
               skip_pass2: bool = False, lm_studio_url: Optional[str] = None,
               agents=None) -> list[dict]:
    if not supplier_id and not (supplier_name and supplier_name.strip()):
        raise ValueError("Give --supplier-id or --supplier-name (needed to group documents "
                         "by supplier; see the module docstring).")
    files = collect_files(paths)
    if not files:
        raise ValueError(f"No supported files ({', '.join(sorted(SUPPORTED))}) found.")

    sid = supplier_id or stable_supplier_id(supplier_name)
    agents = agents or _Agents()
    agents.sqlite.create_supplier(sid, supplier_name)
    print(f"\nSupplier: {sid}" + (" (derived from the name)" if not supplier_id else ""))
    print(f"Files   : {len(files)}\n")

    rows = []
    for f in files:
        print(f"→ {f.name}")
        rows.append(ingest_file(f, sid, supplier_name, agents, skip_pass2, lm_studio_url))
        r = rows[-1]
        print(f"   {r['status']} · {r['chunks']} chunks · pass 2: {r['pass2']}"
              + (f" · {r['note']}" if r["note"] else ""))
    return rows


def _summary(rows: list[dict], supplier_id: str) -> int:
    ok = sum(r["status"] == "ok" for r in rows)
    dup = sum(r["status"] == "duplicate" for r in rows)
    bad = sum(r["status"] == "FAILED" for r in rows)
    degraded = sum(r["pass2"] == "degraded" for r in rows)
    print(f"\n=== Done: {ok} ingested · {dup} duplicate · {bad} failed ===")
    if degraded:
        print(f"{degraded} document(s) were stored but LLM extraction did not complete "
              "(LM Studio unreachable or unusable output). Their certificates and dates are "
              "NOT in the supplier profile yet. Re-run Pass 2 once LM Studio is available.")
    if ok or dup:
        print(f"\nNext: start the API and UI, open supplier {supplier_id}, and run the evaluation.")
    return 1 if bad else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ingest supplier documents (Agent 1 → Agent 2)")
    ap.add_argument("paths", nargs="+", help="file(s) and/or folder(s) of PDF/DOCX")
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--supplier-id", help="your own stable supplier ID (preferred)")
    who.add_argument("--supplier-name", help="supplier name; a stable ID is derived from it")
    ap.add_argument("--skip-pass2", action="store_true", help="store and index only, skip LLM extraction")
    ap.add_argument("--lm-studio-url", default=None)
    a = ap.parse_args()
    try:
        results = run_ingest(a.paths, a.supplier_id, a.supplier_name, a.skip_pass2, a.lm_studio_url)
    except (ValueError, FileNotFoundError) as e:
        raise SystemExit(f"Error: {e}")
    sid = a.supplier_id or stable_supplier_id(a.supplier_name)
    raise SystemExit(_summary(results, sid))
