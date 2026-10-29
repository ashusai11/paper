"""
ingest.py — the unified front door: ANY file in, stored and searchable out.
==========================================================================

    one file  →  sniff the type  →  pick the lane  →  store  →  index
                     │                  │              │         │
                     │                  │              │         └─ ChromaDB chunks
                     │                  │              └─────────── SQLite (documents + tables)
                     │                  │
                     │   document  →  Agent 1 (anydoc/OCR) → Agent 2 pass 1 + pass 2 (LLM)
                     │   tabular   →  route → map → refine → target table + raw mirror
                     │   raw       →  store the bytes, index a descriptor, flag for review
                     │
                     └─ nothing is ever refused

Why three lanes? A spreadsheet is not a document (flattening it destroys the
grid), and a binary file is neither. But all three end in the same two
places — the SQLite file (the system of record) and the ChromaDB index
(rebuildable) — so the search and the LLM never have to care where the
content came from.

The lanes
---------
document  PDF, DOCX, PPTX, ODT, TXT, MD, HTML
          Agent 1 parses offline (OCR for scans) → Agent 2 pass 1 stores,
          chunks, embeds → pass 2 runs the LLM refinery, which produces the
          `profile_facts` the VA26 criteria are built on.

tabular   CSV, TSV, XLSX, XLSM, JSON, JSONL, XML
          Routed to a target table (purchase history, risk matrix, NC
          register, …), mapped column by column, refined in Python, written
          to the table with row-level provenance, and mirrored raw. The same
          rows become search chunks with the header repeated.

raw       everything else (images, archives, legacy .doc/.xls, binaries)
          The bytes are hashed and stored as a document, a descriptor chunk
          is indexed so the file can be found by name, and the import is
          flagged for review. The pipeline never says "unsupported".

Usage
-----
    python ingest.py anything.xlsx --supplier-id SUP-acme-001
    python ingest.py report.pdf     --supplier-name "Acme Medizintechnik GmbH"
    python ingest.py ./inbox/       --supplier-id SUP-acme-001 --dry-run

`run_pipeline.py` still exists and still does the document lane only —
this script is the superset.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from typing import Any, Optional

_ROOT = Path(__file__).resolve().parent
for _p in (_ROOT, _ROOT / "agent2_vectorstore"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── file type sniffing (content first, extension as fallback) ────────────────

# Anything anydoc can convert to markdown belongs to the document lane —
# it also reads .doc, .ppt, .epub, .ods, .odp and legacy .xls/.doc.
DOCUMENT_TYPES = {"pdf", "docx", "pptx", "odt", "rtf", "txt", "md", "html",
                  "doc", "docm", "ppt", "pptm", "epub", "ods", "odp",
                  "doc_legacy", "xls_legacy"}
TABULAR_TYPES = {"csv", "tsv", "xlsx", "xlsm", "json", "jsonl", "xml"}
EXTENSION_TYPES = {
    ".pdf": "pdf", ".docx": "docx", ".doc": "doc_legacy", ".docm": "docm",
    ".pptx": "pptx", ".ppt": "ppt", ".pptm": "pptm", ".epub": "epub",
    ".ods": "ods", ".odp": "odp", ".odt": "odt", ".rtf": "rtf", ".txt": "txt",
    ".md": "md", ".markdown": "md", ".html": "html", ".htm": "html",
    ".epub": "epub", ".ods": "ods", ".odp": "odp",
    ".csv": "csv", ".tsv": "tsv", ".txt.table": "csv", ".xlsx": "xlsx",
    ".xlsm": "xlsm", ".xls": "xls_legacy", ".json": "json", ".jsonl": "jsonl",
    ".ndjson": "jsonl", ".xml": "xml",
}


def sniff_type(path: Path) -> str:
    """Detect the file type from its content; the extension is the fallback.

    Returns one of: pdf, docx, pptx, odt, xlsx, xlsm, doc_legacy, xls_legacy,
    csv, json, jsonl, xml, text, binary.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    try:
        head = path.open("rb").read(4096)
    except OSError:
        return EXTENSION_TYPES.get(suffix, "binary")

    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"PK\x03\x04"):
        # OOXML container — look inside for the part that names the type
        try:
            with zipfile.ZipFile(path) as zf:
                names = set(zf.namelist())
            if any(n.startswith("word/") for n in names):
                return "docx"
            if any(n.startswith("xl/") for n in names):
                return "xlsm" if any("vbaProject" in n for n in names) else "xlsx"
            if any(n.startswith("ppt/") for n in names):
                return "pptx"
        except zipfile.BadZipFile:
            return "binary"
        return "binary"
    if head.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"):
        # legacy OLE2 container (.doc / .xls) — anydoc reads both
        return "xls_legacy" if suffix == ".xls" else "doc_legacy"
    if head.startswith(b"{") or head.startswith(b"["):
        return "json"
    if head.startswith(b"<?xml") or (head.startswith(b"<") and b"<" in head):
        return "xml"
    try:
        head.decode("utf-8")
    except UnicodeDecodeError:
        return EXTENSION_TYPES.get(suffix, "binary")
    # Text content: the extension decides. A CSV and a TXT are both "text",
    # but one is a table and the other is a document.
    return EXTENSION_TYPES.get(suffix, "text")


def pick_lane(file_type: str) -> str:
    """document | tabular | raw"""
    if file_type in DOCUMENT_TYPES:
        return "document"
    if file_type in TABULAR_TYPES:
        return "tabular"
    return "raw"


# ── lazy agent loading (same pattern as run_pipeline.py) ─────────────────────

class _Agents:
    """Agent 1 / Agent 2 entry points and the shared stores.

    Agent 1 (the document parser) is loaded **lazily**: a spreadsheet-only
    install does not need anydoc/OCR, and the document lane reports a clear
    error instead of the whole front door failing to start.
    """

    def __init__(self, need_embedder: bool = True) -> None:
        try:
            spec = importlib.util.spec_from_file_location(
                "agent2_main", _ROOT / "agent2_vectorstore" / "main.py")
            agent2 = importlib.util.module_from_spec(spec)
            sys.modules["agent2_main"] = agent2   # both agents have a main.py
            spec.loader.exec_module(agent2)
            from config import get_chroma_path, get_data_dir
            from embeddings.bge_m3_embeddings import BGE_M3_Embeddings
            from storage.chromadb_store import ChromaDBStore
            from storage.sqlite_store import SQLiteStore
        except ImportError as e:
            raise SystemExit(
                f"Missing dependency: {e}\n"
                f"Install with: pip install -r requirements.txt")

        self.pass1 = agent2.agent2_pass1
        self.pass2 = agent2.agent2_pass2
        self.out_dir = get_data_dir() / "parsed_documents"
        self.out_dir.mkdir(parents=True, exist_ok=True)

        self.sqlite = SQLiteStore()
        self.sqlite.initialize()
        self.chroma = ChromaDBStore(persist_directory=str(get_chroma_path()))
        self.chroma.initialize()
        self.embedder = None
        if need_embedder:
            self.embedder = BGE_M3_Embeddings()
        self._parse_document = None

    @property
    def parse_document(self):
        """Agent 1's parser, loaded on first use (document lane only)."""
        if self._parse_document is None:
            try:
                import agent1_offline.main as agent1
            except ImportError as e:
                raise SystemExit(
                    f"Missing dependency for document parsing: {e}\n"
                    f"Install with: pip install -r requirements.txt")
            self._parse_document = agent1.parse_document
        return self._parse_document


# ── lanes ───────────────────────────────────────────────────────────────────

def _ingest_document(path: Path, supplier_id: str, supplier_name: Optional[str],
                    agents: _Agents, llm_refine: bool = True,
                    lm_studio_url: Optional[str] = None) -> dict:
    """PDF / DOCX / … → Agent 1 → Agent 2 pass 1 (+ pass 2 with the LLM)."""
    parsed = agents.parse_document(str(path), output_dir=str(agents.out_dir))
    p1 = agents.pass1(
        markdown=parsed["full_markdown"], file_path=path,
        supplier_id=supplier_id, supplier_name=supplier_name,
        sqlite_store=agents.sqlite, chroma_store=agents.chroma,
        embedder=agents.embedder,
        json_blob=json.dumps(parsed, default=str),
        page_count=parsed.get("page_count"), doc_format=parsed.get("format"),
    )
    result = {
        "ok": True, "lane": "document",
        "document_id": p1["document_id"], "supplier_id": supplier_id,
        "is_duplicate": bool(p1.get("is_duplicate")),
        "chunks_created": p1.get("chunks_created", 0),
        "pages": parsed.get("page_count"),
        "tables": [], "rows": {},
        "llm_refined": False, "degraded": False, "degraded_reason": None,
    }
    if p1.get("is_duplicate") or not llm_refine:
        return result

    p2 = agents.pass2(document_id=p1["document_id"], supplier_id=supplier_id,
                      sqlite_store=agents.sqlite, chroma_store=agents.chroma,
                      embedder=agents.embedder, lm_studio_url=lm_studio_url)
    result["llm_refined"] = bool(p2.get("refined"))
    result["doc_type"] = p2.get("doc_type")
    if not p2.get("refined"):
        result["degraded"] = True
        result["degraded_reason"] = (
            f"LLM extraction did not complete: {p2.get('status') or 'unknown'}")
    return result


def _ingest_tabular(path: Path, supplier_id: str, supplier_name: Optional[str],
                    target_table: Optional[str] = None, dry_run: bool = False,
                    embed: bool = True, llm_refine: bool = True,
                    agents: Optional[_Agents] = None) -> dict:
    """CSV / XLSX / JSON / XML → target table + raw mirror + chunks."""
    from agent2_vectorstore.tabular.ingest import ingest_tabular as _ingest

    report = _ingest(
        path, supplier_id=supplier_id, supplier_name=supplier_name,
        target_table=target_table, dry_run=dry_run, embed=embed,
        chroma_store=agents.chroma if agents else None,
        embedder=agents.embedder if agents else None,
    )
    result = {
        "ok": bool(report.get("ok")), "lane": "tabular",
        "document_id": report.get("document_id"), "supplier_id": supplier_id,
        "is_duplicate": bool(report.get("is_duplicate")),
        "chunks_created": report.get("chunks_created", 0),
        "tables": [s.get("target_table") for s in report.get("sheets", [])],
        "rows": {s.get("name"): s.get("rows") for s in report.get("sheets", [])},
        "sheets": report.get("sheets", []),
        "degraded": bool(report.get("degraded")),
        "degraded_reason": report.get("degraded_reason"),
        "llm_refined": False,
    }
    if not report.get("ok") or dry_run or not llm_refine:
        return result

    # The LLM layer must see tabular content too — otherwise a certificate
    # or an NC that lives in a spreadsheet never becomes a `profile_fact`.
    # Only for single-supplier files: in a multi-vendor export the facts
    # would belong to a vendor, not to the supplier the file was uploaded for.
    multi_supplier = any(
        (s.get("route") or {}).get("method", "").endswith("+multi_supplier")
        for s in report.get("sheets", [])
    )
    if multi_supplier:
        result["degraded_reason"] = (
            "multi-vendor file — LLM refinement skipped, the tables hold the data")
        return result

    agents = agents or _Agents(need_embedder=False)
    try:
        p2 = agents.pass2(document_id=report["document_id"], supplier_id=supplier_id,
                          sqlite_store=agents.sqlite, chroma_store=agents.chroma,
                          embedder=agents.embedder)
        result["llm_refined"] = bool(p2.get("refined"))
        if not p2.get("refined"):
            result["degraded"] = True
            result["degraded_reason"] = (
                f"LLM extraction did not complete: {p2.get('status') or 'unknown'}")
    except Exception as exc:
        result["degraded"] = True
        result["degraded_reason"] = f"LLM refinement failed: {exc}"
    return result


def _ingest_raw(path: Path, supplier_id: str, supplier_name: Optional[str],
                file_type: str, agents: _Agents) -> dict:
    """Anything else: store the file, index a descriptor, flag for review.

    The pipeline never refuses a file. The content is not parsed (there is
    nothing to parse), but the file is hashed, stored as a document and made
    findable by name — so a reviewer can see that it arrived and what to do
    with it.
    """
    data = path.read_bytes()
    digest = hashlib.sha256(data).hexdigest()
    descriptor = (
        f"File: {path.name}\n"
        f"Type: {file_type} (not parsed as text)\n"
        f"Size: {len(data)} bytes\n"
        f"SHA-256: {digest}\n"
        f"Stored for review — the content could not be parsed into text."
    )
    document_id, is_new = agents.sqlite.store_document(
        supplier_id=supplier_id, file_path=path, markdown=descriptor,
        json_blob=json.dumps({"file_type": file_type, "size": len(data),
                              "sha256": digest}),
        page_count=1, doc_format=file_type, supplier_name=supplier_name,
    )
    chunks = 0
    if agents.embedder is not None:
        try:
            from chunker.text_chunker import stable_chunk_id

            chunk_id = stable_chunk_id(supplier_id, document_id, "raw", 0, descriptor)
            embedding = agents.embedder.embed([descriptor])
            agents.chroma.upsert_chunks(
                [{"id": chunk_id, "text": descriptor,
                  "metadata": {"supplier_id": supplier_id,
                               "supplier_name": supplier_name or "unknown",
                               "document_id": document_id,
                               "document_type": "raw", "doc_type": "raw",
                               "chunk_type": "raw", "chunk_index": 0,
                               "source_file": path.name,
                               "source_format": file_type}}],
                embedding)
            agents.sqlite.store_chunk(document_id=document_id, chunk_id=chunk_id,
                                      chunk_index=0, text=descriptor)
            chunks = 1
        except Exception:
            chunks = 0
    return {
        "ok": True, "lane": "raw", "detected_type": file_type,
        "document_id": document_id, "supplier_id": supplier_id,
        "is_duplicate": not is_new, "chunks_created": chunks,
        "tables": [], "rows": {},
        "needs_review": True,
        "degraded": False, "degraded_reason": None,
        "llm_refined": False,
    }


# ── the front door ──────────────────────────────────────────────────────────

def ingest_any(path: Path | str, supplier_id: Optional[str] = None,
               supplier_name: Optional[str] = None,
               target_table: Optional[str] = None,
               dry_run: bool = False, embed: bool = True,
               llm_refine: bool = True, agents: Optional[_Agents] = None,
               lm_studio_url: Optional[str] = None) -> dict:
    """Ingest any file. Picks the lane, stores it, indexes it, reports it.

    Never raises for an unsupported file type — the raw lane catches it.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"file not found: {path}")
    if not supplier_id and not (supplier_name and supplier_name.strip()):
        raise ValueError("supplier_id or supplier_name is required")

    if supplier_id is None:
        import re as _re
        digest = hashlib.sha1(supplier_name.strip().lower().encode()).hexdigest()[:8]
        slug = _re.sub(r"[^a-z0-9]+", "-", supplier_name.lower()).strip("-")[:32]
        supplier_id = f"SUP-{slug or 'supplier'}-{digest}"

    file_type = sniff_type(path)
    lane = pick_lane(file_type)

    if lane == "document":
        agents = agents or _Agents(need_embedder=embed)
        result = _ingest_document(path, supplier_id, supplier_name, agents,
                                  llm_refine=llm_refine,
                                  lm_studio_url=lm_studio_url)
    elif lane == "tabular":
        agents = agents or _Agents(need_embedder=embed)
        result = _ingest_tabular(path, supplier_id, supplier_name,
                                 target_table=target_table, dry_run=dry_run,
                                 embed=embed, llm_refine=llm_refine, agents=agents)
    else:
        agents = agents or _Agents(need_embedder=embed)
        result = _ingest_raw(path, supplier_id, supplier_name, file_type, agents)

    result.setdefault("file", path.name)
    result["file"] = path.name
    result["detected_type"] = file_type
    result["lane"] = lane
    result["supplier_id"] = supplier_id
    result["dry_run"] = dry_run
    return result


# ── CLI ─────────────────────────────────────────────────────────────────────

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="ingest.py",
        description="Ingest ANY file into the supplier pipeline "
                    "(documents, spreadsheets, JSON/XML, binaries).")
    parser.add_argument("paths", nargs="+", help="file(s) and/or folder(s)")
    who = parser.add_mutually_exclusive_group(required=True)
    who.add_argument("--supplier-id", help="your own stable supplier ID")
    who.add_argument("--supplier-name", help="a stable ID is derived from the name")
    parser.add_argument("--target-table", default=None,
                        help="force the target table for a spreadsheet")
    parser.add_argument("--no-llm-refine", action="store_true",
                        help="store and index only, skip the LLM extraction")
    parser.add_argument("--no-embed", action="store_true",
                        help="store only, skip embedding/indexing")
    parser.add_argument("--dry-run", action="store_true",
                        help="spreadsheets only: preview without writing")
    parser.add_argument("--lm-studio-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(f for f in p.iterdir() if f.is_file()))
        elif p.is_file():
            files.append(p)
        else:
            raise SystemExit(f"Error: not found: {raw}")
    if not files:
        raise SystemExit("Error: no files found.")

    results = []
    for f in files:
        result = ingest_any(
            f, supplier_id=args.supplier_id, supplier_name=args.supplier_name,
            target_table=args.target_table, dry_run=args.dry_run,
            embed=not args.no_embed, llm_refine=not args.no_llm_refine,
            lm_studio_url=args.lm_studio_url,
        )
        results.append(result)
        if not args.json:
            print(f"→ {f.name}")
            print(f"   lane={result['lane']} type={result['detected_type']} "
                  f"chunks={result.get('chunks_created', 0)} "
                  f"llm={'yes' if result.get('llm_refined') else 'no'}")
            if result.get("tables"):
                print(f"   tables: {', '.join(result['tables'])}")
            if result.get("rows"):
                for sheet, counts in result["rows"].items():
                    print(f"   rows[{sheet}]: {counts}")
            if result.get("degraded_reason"):
                print(f"   ! {result['degraded_reason']}")

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False, default=str))

    failed = [r for r in results if not r.get("ok")]
    print(f"\n=== {len(results) - len(failed)} ingested · {len(failed)} failed ===")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
