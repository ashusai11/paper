"""
Agent 2: Vector Store Manager
============================
Store documents from Agent 1 in ChromaDB + SQLite.

Two-Phase Architecture (V3 integration):
  Phase 1 (Ingestion):  Store doc + chunk + embed + ChromaDB (no LLM needed)
  Phase 2 (Refinery):   Classify + LLM extract + refine data + profile + facts

Phase 1 runs automatically for every document.
Phase 2 runs automatically if LM Studio is available, skipped gracefully if not.

Modes:
1. FULL MODE: You provide supplier_id -> links to existing/new supplier
2. DOCUMENT-ONLY MODE: Auto-generate supplier_id -> store now, link later

Usage:
    # Legacy CLI (runs Phase 1 only, backward compatible)
    python main.py markdown.md --supplier-id SUP001 --supplier-name "Acme"

    # Programmatic API
    from agent2_vectorstore.main import agent2_pass1, agent2_pass2
    result = agent2_pass1(markdown, supplier_id, file_path, ...)
    result = agent2_pass2(document_id, supplier_id, ...)

    # Hybrid search
    from agent2_vectorstore.main import hybrid_search
    results = hybrid_search(query_text, query_embedding, supplier_id="SUP001")
"""

import argparse
import hashlib
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from chunker.text_chunker import TextChunker, stable_chunk_id, detect_chunk_type, detect_language
from embeddings.bge_m3_embeddings import BGE_M3_Embeddings
from storage.sqlite_store import SQLiteStore
from storage.chromadb_store import ChromaDBStore


def _get_chroma_path():
    """D8 FIX: resolve ChromaDB path from config.py"""
    import sys
    from pathlib import Path as _P
    here = _P(__file__).resolve().parent
    for c in [here, here.parent, here.parent.parent]:
        if (c / "config.py").exists():
            if str(c) not in sys.path: sys.path.insert(0, str(c))
            from config import get_chroma_path
            return get_chroma_path()
    return here.parent / "data" / "chroma"


def generate_supplier_id(file_path: str) -> str:
    """Generate a stable supplier ID from file content hash."""
    content = f"{file_path}_{datetime.now().date().isoformat()}"
    hash_value = hashlib.md5(content.encode()).hexdigest()[:8].upper()
    return f"AUTO_{hash_value}"


# ====================================================================
# Phase 1: Ingestion (no LLM needed)
# ====================================================================

def agent2_pass1(
    markdown: str,
    file_path: Path,
    supplier_id: str,
    supplier_name: str = None,
    sqlite_store: SQLiteStore = None,
    chroma_store: ChromaDBStore = None,
    embedder: BGE_M3_Embeddings = None,
    chunker: TextChunker = None,
    json_blob: str = None,
    page_count: int = None,
    doc_format: str = None,
) -> dict:
    """
    Phase 1: Ingest document into SQLite + ChromaDB.

    Steps:
    1. Store original document in SQLite (SHA-256 dedup, auto-version)
    2. Chunk document using 4-level cascade chunker
    3. Generate BGE-M3 embeddings
    4. Store chunks in ChromaDB + SQLite

    Args:
        markdown: Full markdown content
        file_path: Original file path
        supplier_id: Supplier ID
        supplier_name: Optional supplier name
        sqlite_store: SQLiteStore instance (created if None)
        chroma_store: ChromaDBStore instance (created if None)
        embedder: BGE_M3_Embeddings instance (created if None)
        chunker: TextChunker instance (created if None)
        json_blob: Optional Agent 1 JSON output
        page_count: Number of pages
        doc_format: Source file format

    Returns:
        {
            "document_id": str,
            "supplier_id": str,
            "chunks_created": int,
            "is_duplicate": bool,
            "phase": "ingestion"
        }
    """
    # Initialize stores if not provided
    if sqlite_store is None:
        sqlite_store = SQLiteStore()  # D8
        sqlite_store.initialize()

    if chroma_store is None:
        chroma_store = ChromaDBStore(persist_directory=str(_get_chroma_path()))  # D8
        chroma_store.initialize()

    if embedder is None:
        embedder = BGE_M3_Embeddings()

    if chunker is None:
        chunker = TextChunker()

    # Step 1: Store original document — atomic (supplier + document + skeleton
    #         refined_data + company_profile bump all in one transaction)
    print("[Phase 1/4] Storing document in SQLite...")
    document_id, is_new = sqlite_store.store_document(
        supplier_id=supplier_id,
        file_path=file_path,
        markdown=markdown,
        json_blob=json_blob,
        page_count=page_count,
        doc_format=doc_format,
        supplier_name=supplier_name,
    )

    is_duplicate = not is_new

    if is_duplicate:
        print(f"  Duplicate content — already stored as {document_id}. Skipping chunks.")
        return {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "chunks_created": 0,
            "is_duplicate": True,
            "phase": "ingestion",
        }

    print(f"  Document ID: {document_id}")

    # Step 2: Chunk document
    print("[Phase 1/4] Chunking document...")

    # Try to use build_chunks_from_parsed if we have a json_blob
    chunks_with_ids = []
    if json_blob:
        try:
            import json as _json
            parsed = _json.loads(json_blob) if isinstance(json_blob, str) else json_blob
            chunks_with_ids = chunker.build_chunks_from_parsed(
                parsed, supplier_id, document_id
            )
        except Exception:
            chunks_with_ids = []

    # Fallback: use markdown-based chunking
    if not chunks_with_ids:
        chunks = chunker.chunk(markdown, metadata={
            "source_file": file_path.name,
            "supplier_id": supplier_id,
            "supplier_name": supplier_name or "unknown",
            "document_id": document_id,
        })

        chunks_with_ids = []
        for chunk in chunks:
            idx = chunk["metadata"].get("chunk_index", 0)
            chunk_type = chunk["metadata"].get("chunk_type", "general")
            chunk_id = stable_chunk_id(
                supplier_id, document_id, chunk_type, idx, chunk["text"]
            )
            chunks_with_ids.append({
                "text": chunk["text"],
                "metadata": chunk["metadata"],
                "id": chunk_id,
            })

    if not chunks_with_ids:
        print("  Warning: No chunks generated")
        return {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "chunks_created": 0,
            "is_duplicate": False,
            "phase": "ingestion",
        }

    print(f"  Created {len(chunks_with_ids)} chunks")

    # Step 3: Generate embeddings
    print("[Phase 1/4] Generating embeddings (BAAI/bge-m3)...")
    texts = [c["text"] for c in chunks_with_ids]
    embeddings = embedder.embed(texts)
    print(f"  Generated {len(embeddings)} embeddings")

    # Step 4: Store in ChromaDB + SQLite (D3 FIX — SQLite is source of truth)
    print("[Phase 1/4] Storing in ChromaDB...")
    chroma_store.upsert_chunks(chunks_with_ids, embeddings)
    print(f"  Stored {len(chunks_with_ids)} chunks in ChromaDB")
    _sqlite_chunks = 0
    for _chunk in chunks_with_ids:
        try:
            sqlite_store.store_chunk(
                document_id=document_id,
                chunk_id=_chunk["id"],
                chunk_index=_chunk["metadata"].get("chunk_index", 0),
                text=_chunk["text"],
            )
            _sqlite_chunks += 1
        except Exception as _e:
            print(f"  Warning: chunk SQLite write failed: {_e}")
    print(f"  {_sqlite_chunks}/{len(chunks_with_ids)} chunks written to SQLite (D3)")

    return {
        "document_id": document_id,
        "supplier_id": supplier_id,
        "chunks_created": len(chunks_with_ids),
        "is_duplicate": False,
        "phase": "ingestion",
    }


# ====================================================================
# Phase 2: Refinery (LLM extraction)
# ====================================================================

def agent2_pass2(
    document_id: str,
    supplier_id: str,
    sqlite_store: SQLiteStore = None,
    chroma_store: ChromaDBStore = None,
    embedder: BGE_M3_Embeddings = None,
    lm_studio_url: str = None,
) -> dict:
    """
    Phase 2: Classify + LLM extract + refine data.

    Steps:
    1. Classify document type (rule-based)
    2. Extract structured data (LM Studio, graceful fallback)
    3. Update refined_data, company_profile, profile_facts
    4. Create refinery chunks in ChromaDB

    Args:
        document_id: Document ID from Phase 1
        supplier_id: Supplier ID
        sqlite_store: SQLiteStore instance
        chroma_store: ChromaDBStore instance
        embedder: BGE_M3_Embeddings instance
        lm_studio_url: Optional custom LM Studio URL

    Returns:
        {
            "document_id": str,
            "supplier_id": str,
            "doc_type": str,
            "llm_used": bool,
            "facts_created": int,
            "chunks_created": int,
            "profile_updated": bool,
            "phase": "refinery"
        }
    """
    if sqlite_store is None:
        sqlite_store = SQLiteStore()  # D8

    if chroma_store is None:
        chroma_store = ChromaDBStore(persist_directory=str(_get_chroma_path()))  # D8

    if embedder is None:
        try:
            embedder = BGE_M3_Embeddings()
        except Exception:
            embedder = None

    # Step 1: Get document
    doc = sqlite_store.get_document(document_id)
    if not doc:
        return {
            "document_id": document_id,
            "supplier_id": supplier_id,
            "status": "document_not_found",
            "phase": "refinery",
        }

    markdown = doc["markdown"]
    source_file = doc.get("file_name", "unknown")

    # Step 2: Classify document type
    print("[Phase 2/4] Classifying document type...")
    from refinery.classifier import classify_document_with_confidence
    classification = classify_document_with_confidence(markdown)
    doc_type = classification["doc_type"]
    print(f"  Type: {doc_type} (confidence: {classification['confidence']})")

    # Step 3: LLM extraction
    print("[Phase 2/4] Extracting structured data...")
    extracted = {}
    llm_used = False

    if lm_studio_url is None:
        # Try default LM Studio
        from refinery.extractor import LMStudioExtractor
        extractor = LMStudioExtractor()
    else:
        from refinery.extractor import LMStudioExtractor
        extractor = LMStudioExtractor(base_url=lm_studio_url)

    if extractor.available():
        print("  LM Studio available, running extraction...")
        extracted = extractor.extract(markdown, doc_type=doc_type)
        if extracted:
            llm_used = True
            print(f"  Extracted {len(extracted)} fields")
        else:
            print("  LLM extraction returned empty")
    else:
        print("  LM Studio not available, using rule-based data only")

    # Always include doc_type from classifier
    extracted["doc_type"] = doc_type

    # Step 4: Refine (update all data layers)
    print("[Phase 2/4] Updating refined data, profile, facts...")
    from refinery.refiner import Refiner
    refiner = Refiner(sqlite_store, chroma_store, embedder)
    refine_result = refiner.refine(
        document_id=document_id,
        extracted=extracted,
        supplier_id=supplier_id,
        source_file=source_file,
    )

    print(f"  Facts created: {refine_result.get('facts_created', 0)}")
    print(f"  Chunks created: {refine_result.get('chunks_created', 0)}")
    print(f"  Profile updated: {refine_result.get('profile_updated', False)}")

    return {
        "document_id": document_id,
        "supplier_id": supplier_id,
        "doc_type": doc_type,
        "llm_used": llm_used,
        **refine_result,
        "phase": "refinery",
    }


# ====================================================================
# Hybrid Search
# ====================================================================

def hybrid_search(
    query_text: str,
    query_embedding: list[float],
    supplier_id: str = None,
    document_id: str = None,
    chunk_type: str = None,
    document_type: str = None,
    n_results: int = 8,
    chroma_store: ChromaDBStore = None,
) -> list[dict]:
    """
    Hybrid search: BM25 + Vector merged via RRF.

    Args:
        query_text: Raw query text (for BM25)
        query_embedding: Query embedding vector (for vector search)
        supplier_id: Optional supplier filter
        document_id: Optional document filter
        chunk_type: Optional chunk type filter
        document_type: Optional document type filter
        n_results: Number of results
        chroma_store: ChromaDBStore instance

    Returns:
        List of result dicts
    """
    if chroma_store is None:
        chroma_store = ChromaDBStore(persist_directory=str(_get_chroma_path()))  # D8
        chroma_store.initialize()

    return chroma_store.hybrid_search(
        query_text=query_text,
        query_embedding=query_embedding,
        n_results=n_results,
        supplier_id=supplier_id,
        document_id=document_id,
        chunk_type=chunk_type,
        document_type=document_type,
    )


# ====================================================================
# Legacy CLI (backward compatible)
# ====================================================================

def main():
    """
    Legacy CLI entry point for Agent 2.

    Runs Phase 1 (ingestion) + Phase 2 (refinery if LM Studio available).
    All original CLI arguments preserved for backward compatibility.
    """
    parser = argparse.ArgumentParser(
        description="Supplier Risk Agent 2 - Vector Store",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Document-only mode (auto-generate supplier ID)
  python main.py output/markdown.md

  # Full mode (you know the supplier)
  python main.py output/markdown.md --supplier-id SUP001

  # Auto-assign with filename-based ID
  python main.py output/markdown.md --auto-supplier

  # Batch mode (one supplier, multiple documents)
  python main.py doc1.md doc2.md --supplier-id SUP001

  # Skip refinery (Phase 2)
  python main.py doc.md --supplier-id SUP001 --skip-refinery
        """
    )

    parser.add_argument(
        "markdown_files",
        nargs="+",
        help="Markdown file(s) generated by Agent 1"
    )

    parser.add_argument(
        "--supplier-id",
        default=None,
        help="Unique supplier ID (auto-generated if not provided)"
    )

    parser.add_argument(
        "--supplier-name",
        default=None,
        help="Supplier name (optional, extracted from doc later)"
    )

    parser.add_argument(
        "--auto-supplier",
        action="store_true",
        help="Auto-generate supplier ID from filename"
    )

    parser.add_argument(
        "--database",
        default=None,  # D8
        help="SQLite database path"
    )

    parser.add_argument(
        "--chroma",
        default=None,  # D8
        help="ChromaDB persistent directory"
    )

    parser.add_argument(
        "--collection",
        default="supplier_documents",
        help="ChromaDB collection name"
    )

    parser.add_argument(
        "--chunk-size",
        type=int,
        default=1000,
        help="Chunk size in characters (legacy)"
    )

    parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=150,
        help="Chunk overlap in characters (legacy)"
    )

    parser.add_argument(
        "--skip-refinery",
        action="store_true",
        help="Skip Phase 2 (refinery) even if LM Studio is available"
    )

    parser.add_argument(
        "--lm-studio-url",
        default=None,
        help="Custom LM Studio API URL"
    )

    args = parser.parse_args()

    # =============================================
    # Determine supplier_id
    # =============================================
    if args.auto_supplier or not args.supplier_id:
        first_file = Path(args.markdown_files[0])
        safe_name = "".join(c for c in first_file.stem if c.isalnum() or c in "-_").upper()
        if len(safe_name) > 20:
            safe_name = safe_name[:20]
        args.supplier_id = f"DOC_{safe_name}"
        args.supplier_name = args.supplier_name or f"Auto-generated: {first_file.name}"

    print("=" * 70)
    print("SUPPLIER RISK AGENT 2 - VECTOR STORE (v2: Two-Phase)")
    print("=" * 70)
    print(f"Supplier:    {args.supplier_id}")
    if args.supplier_name:
        print(f"Name:        {args.supplier_name}")
    print(f"Database:    {args.database}")
    print(f"ChromaDB:    {args.chroma}")
    print(f"Files:       {len(args.markdown_files)}")
    print(f"Refinery:    {'skip' if args.skip_refinery else 'auto (if LM Studio available)'}")
    print("=" * 70)

    # =============================================
    # Initialize stores
    # =============================================
    print("\n[SETUP] Initializing databases...")

    try:
        sqlite_store = SQLiteStore(args.database)
        sqlite_store.initialize()

        chroma_store = ChromaDBStore(
            persist_directory=args.chroma,
            collection_name=args.collection
        )
        chroma_store.initialize()

        embedder = BGE_M3_Embeddings()
        chunker = TextChunker(
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap
        )

        print("   OK SQLite initialized")
        print("   OK ChromaDB initialized")

    except Exception as e:
        print(f"Error initializing stores: {e}")
        sys.exit(1)

    # =============================================
    # Create/update supplier
    # =============================================
    print(f"\n[SUPPLIER] Creating/Updating: {args.supplier_id}")

    try:
        sqlite_store.create_supplier(
            supplier_id=args.supplier_id,
            supplier_name=args.supplier_name
        )
        print(f"   OK Supplier registered")
    except Exception as e:
        print(f"Error creating supplier: {e}")
        sys.exit(1)

    # =============================================
    # Process each file
    # =============================================
    all_document_ids = []
    total_chunks = 0

    for file_index, markdown_file in enumerate(args.markdown_files, 1):
        print(f"\n{'='*70}")
        print(f"[FILE {file_index}/{len(args.markdown_files)}] {Path(markdown_file).name}")
        print("="*70)

        markdown_path = Path(markdown_file)

        if not markdown_path.exists():
            print(f"   Skipping: File not found")
            continue

        # Read Markdown
        print("\n[PHASE 1] Reading markdown...")

        try:
            markdown = markdown_path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"   Error reading file: {e}")
            continue

        if not markdown.strip():
            print("   Error: Markdown is empty")
            continue

        print(f"   Loaded {len(markdown)} characters")

        # --- Phase 1: Ingestion ---
        try:
            result = agent2_pass1(
                markdown=markdown,
                file_path=markdown_path,
                supplier_id=args.supplier_id,
                supplier_name=args.supplier_name,
                sqlite_store=sqlite_store,
                chroma_store=chroma_store,
                embedder=embedder,
                chunker=chunker,
            )

            document_id = result["document_id"]
            all_document_ids.append(document_id)
            total_chunks += result["chunks_created"]

            print(f"   Phase 1 complete: {result['chunks_created']} chunks")

        except Exception as e:
            print(f"   Error in Phase 1: {e}")
            continue

        # --- Phase 2: Refinery (automatic) ---
        if not args.skip_refinery:
            print(f"\n[PHASE 2] Refinement for {document_id[:8]}...")
            try:
                pass2_result = agent2_pass2(
                    document_id=document_id,
                    supplier_id=args.supplier_id,
                    sqlite_store=sqlite_store,
                    chroma_store=chroma_store,
                    embedder=embedder,
                    lm_studio_url=args.lm_studio_url,
                )
                print(f"   Phase 2 complete: doc_type={pass2_result.get('doc_type', 'unknown')}, "
                      f"llm={'yes' if pass2_result.get('llm_used') else 'no'}")
            except Exception as e:
                print(f"   Phase 2 error (non-fatal): {e}")

    # =============================================
    # Summary
    # =============================================
    print("\n" + "=" * 70)
    print("AGENT 2 COMPLETE")
    print("=" * 70)
    print(f"  Supplier ID:      {args.supplier_id}")
    print(f"  Supplier Name:    {args.supplier_name or '(not provided)'}")
    print(f"  Documents:        {len(all_document_ids)}")
    print(f"  Total Chunks:     {total_chunks}")
    print(f"  SQLite:           {args.database}")
    print(f"  ChromaDB:         {args.chroma}/{args.collection}")
    print("=" * 70)

    if all_document_ids:
        print("\nDocument IDs (save these for later):")
        for doc_id in all_document_ids:
            print(f"   {doc_id}")

    print("\nNEXT STEPS:")
    print(f"  1. To link to existing supplier:")
    print(f"     python main.py new_doc.md --supplier-id {args.supplier_id}")
    print()
    print(f"  2. To search documents (hybrid):")
    print(f"     from agent2_vectorstore.main import hybrid_search")
    print(f"     results = hybrid_search(query_text, query_embedding, supplier_id='{args.supplier_id}')")


if __name__ == "__main__":
    main()
