"""
ChromaDBStore
==============
ChromaDB vector store wrapper with hybrid search.

Features:
- Persistent storage
- Cosine similarity
- Metadata filtering (supplier_id, document_id, chunk_type, document_type)
- Upsert support (handles re-uploads)
- Supplier-based queries
- Hybrid BM25 + Vector search with Reciprocal Rank Fusion (RRF)

Improvements (v3 integration):
- BM25 keyword search using rank_bm25
- RRF merge with configurable BM25 weight (1.8)
- Enhanced filtering: document_id, chunk_type, document_type
- Batch upsert for efficiency
- Supplier-scoped BM25 (only scores docs for the supplier)

Install:
    pip install chromadb rank_bm25

Usage:
    store = ChromaDBStore(persist_directory="./data/chroma")
    store.initialize()
    store.upsert_chunk(chunk_id, text, embedding, metadata)
    results = store.search(query_embedding, supplier_id="SUP001")
    hybrid_results = store.hybrid_search(query_text, query_embedding, supplier_id="SUP001")
"""

from typing import Optional

import chromadb

try:
    from rank_bm25 import BM25Okapi
    BM25_AVAILABLE = True
except ImportError:
    BM25Okapi = None
    BM25_AVAILABLE = False


# RRF configuration
BM25_WEIGHT = 1.8  # BM25 results get 1.8x weight in RRF
RRF_K = 60  # RRF constant (higher = more even weighting)


def _simple_tokenize(text: str) -> list[str]:
    """Simple whitespace + alphanumeric tokenizer for BM25."""
    import re
    tokens = re.findall(r"\b\w+\b", (text or "").lower())
    return [t for t in tokens if len(t) > 2]


class ChromaDBStore:
    """
    ChromaDB vector store wrapper with hybrid search.

    Uses cosine similarity for semantic search.
    Supports hybrid BM25 + vector search merged via RRF.

    Usage:
        store = ChromaDBStore(persist_directory="./data/chroma")
        store.initialize()
        store.upsert_chunk(chunk_id, text, embedding, metadata)
        results = store.search(query_embedding, supplier_id="SUP001")
        hybrid_results = store.hybrid_search(query_text, query_embedding, supplier_id="SUP001")
    """

    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "supplier_documents",
    ):
        """
        Initialize ChromaDB store.

        Args:
            persist_directory: Directory for persistent storage
            collection_name: Name of the collection
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        self.client = None
        self.collection = None

    def initialize(self):
        """Initialize ChromaDB client and collection."""
        self.client = chromadb.PersistentClient(
            path=self.persist_directory
        )

        # Create collection with cosine similarity
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={
                "description": "Supplier document chunks",
                "hnsw:space": "cosine",
            }
        )

    def _ensure_init(self):
        """Ensure collection is initialized."""
        if self.collection is None:
            self.initialize()

    def upsert_chunk(
        self,
        chunk_id: str,
        text: str,
        embedding: list[float],
        metadata: dict,
    ):
        """
        Add or update a chunk.

        Uses upsert so re-uploading same chunk updates it,
        doesn't create duplicates.

        Args:
            chunk_id: Unique chunk ID
            text: Chunk text
            embedding: Embedding vector
            metadata: Metadata dict
        """
        self._ensure_init()

        self.collection.upsert(
            ids=[chunk_id],
            documents=[text],
            embeddings=[embedding],
            metadatas=[metadata]
        )

    def upsert_chunks(
        self,
        chunks: list[dict],
        embeddings: list[list[float]],
    ) -> int:
        """
        Batch upsert multiple chunks.

        Args:
            chunks: List of dicts with 'id', 'text', 'metadata'
            embeddings: List of embedding vectors

        Returns:
            Number of chunks upserted
        """
        if not chunks:
            return 0

        self._ensure_init()

        self.collection.upsert(
            ids=[c["id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            embeddings=embeddings,
            metadatas=[c["metadata"] for c in chunks],
        )

        return len(chunks)

    def add_chunk(
        self,
        chunk_id: str,
        text: str,
        embedding: list[float],
        metadata: dict,
    ):
        """
        Add a chunk (alias for upsert for backward compatibility).
        """
        self.upsert_chunk(chunk_id, text, embedding, metadata)

    def _build_where(
        self,
        supplier_id: str = None,
        document_id: str = None,
        chunk_type: str = None,
        document_type: str = None,
    ) -> Optional[dict]:
        """
        Build ChromaDB where filter from parameters.

        Supports single-field or multi-field filters.
        """
        conditions = []

        if supplier_id:
            conditions.append({"supplier_id": supplier_id})
        if document_id:
            conditions.append({"document_id": document_id})
        if chunk_type:
            conditions.append({"chunk_type": chunk_type})
        if document_type:
            conditions.append({"document_type": document_type})

        if not conditions:
            return None

        if len(conditions) == 1:
            return conditions[0]

        return {"$and": conditions}

    def search(
        self,
        query_embedding: list[float],
        n_results: int = 5,
        supplier_id: str = None,
        document_id: str = None,
        chunk_type: str = None,
        document_type: str = None,
    ) -> dict:
        """
        Vector-only search for similar chunks.

        Args:
            query_embedding: Query embedding vector
            n_results: Number of results to return
            supplier_id: Optional supplier filter
            document_id: Optional document filter
            chunk_type: Optional chunk type filter
            document_type: Optional document type filter

        Returns:
            ChromaDB query results with documents, metadatas, distances
        """
        self._ensure_init()

        where = self._build_where(supplier_id, document_id, chunk_type, document_type)

        return self.collection.query(
            query_embeddings=[query_embedding],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float],
        n_results: int = 5,
        supplier_id: str = None,
        document_id: str = None,
        chunk_type: str = None,
        document_type: str = None,
    ) -> list[dict]:
        """
        Hybrid search: vector + BM25 merged via Reciprocal Rank Fusion.

        1. Fetch all candidate docs for the scope (supplier/document/type filter)
        2. Score with BM25 on query text
        3. Score with vector similarity
        4. Merge rankings via RRF (BM25 gets 1.8x weight)
        5. Return top n_results

        Degrades to vector-only if rank_bm25 not installed.

        Args:
            query_text: Raw query text for BM25 scoring
            query_embedding: Query embedding vector
            n_results: Number of results to return
            supplier_id: Optional supplier filter
            document_id: Optional document filter
            chunk_type: Optional chunk type filter
            document_type: Optional document type filter

        Returns:
            List of result dicts with 'id', 'text', 'metadata', 'distance', 'score'
        """
        self._ensure_init()

        if self.collection.count() == 0:
            return []

        where = self._build_where(supplier_id, document_id, chunk_type, document_type)

        # Fetch all candidate docs for the scope
        all_results = self.collection.get(
            where=where,
            include=["documents", "metadatas"],
        )

        if not all_results["ids"] or not all_results["documents"]:
            return []

        all_docs = [
            {
                "id": all_results["ids"][i],
                "text": doc,
                "metadata": all_results["metadatas"][i] if all_results["metadatas"] else {},
            }
            for i, doc in enumerate(all_results["documents"])
            if doc
        ]

        if not all_docs:
            return []

        # Vector search (wider net for RRF)
        result_limit = min(max(n_results * 3, 10), len(all_docs))

        try:
            vector_results = self.collection.query(
                query_embeddings=[query_embedding],
                where=where,
                n_results=result_limit,
                include=["documents", "metadatas", "distances"],
            )

            # Flatten vector results
            vector_hits = []
            v_ids = vector_results.get("ids", [[]])[0]
            v_docs = vector_results.get("documents", [[]])[0]
            v_metas = vector_results.get("metadatas", [[]])[0]
            v_dists = vector_results.get("distances", [[]])[0]

            for i, doc in enumerate(v_docs):
                vector_hits.append({
                    "id": v_ids[i] if i < len(v_ids) else "",
                    "text": doc,
                    "metadata": v_metas[i] if i < len(v_metas) else {},
                    "distance": v_dists[i] if i < len(v_dists) else None,
                })
        except Exception:
            vector_hits = []

        # BM25 search
        keyword_hits = []
        if BM25_AVAILABLE and all_docs:
            keyword_hits = self._bm25_rank(query_text, all_docs, limit=result_limit)

        # RRF merge
        if keyword_hits:
            return self._rrf_merge(vector_hits, keyword_hits, n_results)

        # Fallback: vector-only
        return vector_hits[:n_results]

    def _bm25_rank(
        self,
        query: str,
        docs: list[dict],
        limit: int,
    ) -> list[dict]:
        """Score and rank docs using BM25Okapi."""
        tokenized = [_simple_tokenize(d["text"]) for d in docs]
        if not any(tokenized):
            return []

        bm25 = BM25Okapi(tokenized)
        scores = bm25.get_scores(_simple_tokenize(query))

        ranked = []
        for i, score in sorted(enumerate(scores), key=lambda x: x[1], reverse=True):
            if score <= 0:
                continue
            item = dict(docs[i])
            item["bm25_score"] = float(score)
            ranked.append(item)
            if len(ranked) >= limit:
                break

        return ranked

    def _rrf_merge(
        self,
        vector_hits: list[dict],
        keyword_hits: list[dict],
        n_results: int,
    ) -> list[dict]:
        """
        Merge vector and keyword results via Reciprocal Rank Fusion.

        RRF formula: score(d) = SUM(1 / (k + rank))
        BM25 hits get BM25_WEIGHT multiplier.
        """
        by_id: dict[str, dict] = {}
        scores: dict[str, float] = {}

        # Vector hits: weight = 1.0
        for rank, hit in enumerate(vector_hits):
            hit_id = hit.get("id", "")
            by_id[hit_id] = hit
            scores[hit_id] = scores.get(hit_id, 0.0) + 1.0 / (RRF_K + rank + 1)

        # Keyword hits: weight = BM25_WEIGHT (1.8)
        for rank, hit in enumerate(keyword_hits):
            hit_id = hit.get("id", "")
            by_id[hit_id] = hit
            scores[hit_id] = scores.get(hit_id, 0.0) + BM25_WEIGHT / (RRF_K + rank + 1)

        ranked_ids = sorted(scores, key=scores.__getitem__, reverse=True)[:n_results]
        return [{**by_id[hid], "score": scores[hid]} for hid in ranked_ids]

    def get(
        self,
        chunk_ids: list[str] = None,
        where: dict = None,
        limit: int = None,
    ) -> dict:
        """
        Get chunks by ID or filter.

        Args:
            chunk_ids: List of chunk IDs
            where: Metadata filter
            limit: Maximum chunks to return

        Returns:
            ChromaDB get results
        """
        self._ensure_init()

        return self.collection.get(
            ids=chunk_ids,
            where=where,
            limit=limit,
            include=["documents", "metadatas"]
        )

    def get_by_supplier(self, supplier_id: str) -> dict:
        """Get all chunks for a supplier."""
        return self.get(where={"supplier_id": supplier_id})

    def delete(
        self,
        chunk_ids: list[str] = None,
        where: dict = None,
    ):
        """Delete chunks by ID or filter."""
        self._ensure_init()
        self.collection.delete(ids=chunk_ids, where=where)

    def delete_by_supplier(self, supplier_id: str):
        """Delete all chunks for a supplier."""
        self.delete(where={"supplier_id": supplier_id})

    def count(self) -> int:
        """Get total chunk count."""
        self._ensure_init()
        return self.collection.count()

    def clear(self):
        """Delete all chunks in the collection."""
        self._ensure_init()
        self.collection.delete(where={})

    def list_suppliers(self) -> list[str]:
        """
        List all unique suppliers in the collection.

        Returns:
            List of supplier IDs
        """
        self._ensure_init()

        results = self.collection.get(
            include=["metadatas"],
            limit=10000
        )

        suppliers = set()
        for metadata in results.get("metadatas", []):
            if metadata and "supplier_id" in metadata:
                suppliers.add(metadata["supplier_id"])

        return sorted(list(suppliers))

    def get_stats(self) -> dict:
        """Get collection statistics."""
        self._ensure_init()

        return {
            "name": self.collection_name,
            "count": self.collection.count(),
            "persist_directory": self.persist_directory,
            "hybrid_search": BM25_AVAILABLE,
            "bm25_weight": BM25_WEIGHT,
        }
