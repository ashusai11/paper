"""
BGE_M3_Embeddings
==================
BAAI/bge-m3 embeddings using FlagEmbedding.

Model: BAAI/bge-m3
- Dimensions: 1024
- Languages: 100+ (including German)
- Max tokens: 8192
- License: MIT

Improvements (v3 integration):
- Singleton model cache (model loaded once, reused across calls)
- fp16 support (halves memory, negligible quality loss)
- Batched encoding with configurable batch size

Install:
    pip install FlagEmbedding

Usage:
    embedder = BGE_M3_Embeddings()
    vectors = embedder.embed(["text1", "text2"])
    query_vec = embedder.embed_query("my query")
"""

from typing import Optional

try:
    import numpy as np
    import FlagEmbedding
    FLAG_EMBEDDING_AVAILABLE = True
except ImportError:
    FLAG_EMBEDDING_AVAILABLE = False
    FlagEmbedding = None
    np = None


# Singleton model cache — model loaded once, reused across all instances
_model_cache = None
_model_cache_config = None


class BGE_M3_Embeddings:
    """
    BAAI/bge-m3 embeddings using FlagEmbedding.

    Optimized for:
    - German + English supplier documents
    - Long documents (up to 8192 tokens)
    - Semantic search

    Uses singleton cache: model loaded once on first call,
    subsequent calls reuse the cached instance.
    """

    MODEL_NAME = "BAAI/bge-m3"
    DIMENSIONS = 1024
    MAX_LENGTH = 8192
    QUERY_LENGTH = 512  # Optimized for queries (shorter)

    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        use_fp16: bool = True,
        batch_size: int = 16,
    ):
        """
        Initialize BGE-M3 embeddings.

        Args:
            model_name: Model name (default: BAAI/bge-m3)
            use_fp16: Use FP16 for faster inference (default: True)
            batch_size: Batch size for encoding (default: 16)
        """
        if not FLAG_EMBEDDING_AVAILABLE:
            raise ImportError(
                "FlagEmbedding is not installed.\n"
                "Install with: pip install FlagEmbedding"
            )

        self.model_name = model_name
        self.use_fp16 = use_fp16
        self.batch_size = batch_size

    def _load_model(self):
        """
        Load model with singleton cache.

        Model is loaded once and cached globally. Subsequent calls
        return the cached instance regardless of how many BGE_M3_Embeddings
        objects exist.
        """
        global _model_cache, _model_cache_config

        config_key = (self.model_name, self.use_fp16)

        if _model_cache is not None and _model_cache_config == config_key:
            return _model_cache

        print(f"[Embeddings] Loading {self.model_name} (fp16={self.use_fp16}, first run may download ~2.2 GB)...")
        _model_cache = FlagEmbedding.BGEM3FlagModel(
            self.model_name,
            use_fp16=self.use_fp16,
        )
        _model_cache_config = config_key
        print("[Embeddings] Model ready.")
        return _model_cache

    def embed(
        self,
        texts: list[str],
        max_length: int = None,
    ) -> list[list[float]]:
        """
        Embed a list of texts (documents).

        Processes in batches to avoid OOM on large ingestions.

        Args:
            texts: List of text strings to embed
            max_length: Max token length (default: 512 for chunks)

        Returns:
            List of dense embedding vectors (1024 dimensions each)
        """
        if not texts:
            return []

        model = self._load_model()
        max_len = max_length or 512

        all_embeddings = []
        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            result = model.encode(
                batch,
                batch_size=len(batch),
                max_length=max_len,
                return_dense=True,
                return_sparse=False,
                return_colbert_vecs=False,
            )
            dense_vecs = result["dense_vecs"]
            all_embeddings.extend(
                dense_vecs.tolist() if hasattr(dense_vecs, 'tolist')
                else [self._to_list(v) for v in dense_vecs]
            )

        return all_embeddings

    def embed_query(
        self,
        query: str,
        max_length: int = None,
    ) -> list[float]:
        """
        Embed a single query string.

        Optimized for short queries (uses shorter max_length).

        Args:
            query: Query text
            max_length: Max token length (default: 512 for queries)

        Returns:
            Single dense embedding vector (1024 dimensions)
        """
        model = self._load_model()
        max_len = max_length or self.QUERY_LENGTH

        result = model.encode(
            [query],
            batch_size=1,
            max_length=max_len,
            return_dense=True,
            return_sparse=False,
            return_colbert_vecs=False,
        )

        vector = result["dense_vecs"][0]
        return self._to_list(vector)

    def embed_with_sparse(
        self,
        texts: list[str],
        max_length: int = None,
    ) -> dict:
        """
        Embed texts with sparse vectors (BM25-like).

        Useful for hybrid search combining dense + sparse.

        Args:
            texts: List of text strings
            max_length: Max token length

        Returns:
            Dictionary with:
            - dense_vecs: List of dense vectors
            - sparse_vecs: List of sparse vectors
        """
        if not texts:
            return {"dense_vecs": [], "sparse_vecs": []}

        model = self._load_model()
        max_len = max_length or self.MAX_LENGTH

        all_dense = []
        all_sparse = []

        for i in range(0, len(texts), self.batch_size):
            batch = texts[i : i + self.batch_size]
            result = model.encode(
                batch,
                batch_size=len(batch),
                max_length=max_len,
                return_dense=True,
                return_sparse=True,
                return_colbert_vecs=False,
            )
            all_dense.extend(
                result["dense_vecs"].tolist()
                if hasattr(result["dense_vecs"], 'tolist')
                else [self._to_list(v) for v in result["dense_vecs"]]
            )
            all_sparse.extend(result["sparse_vecs"])

        return {"dense_vecs": all_dense, "sparse_vecs": all_sparse}

    def _to_list(self, vector) -> list[float]:
        """Convert numpy array or list to list of floats."""
        if np is not None and isinstance(vector, np.ndarray):
            return vector.tolist()
        return list(vector)

    def get_dimension(self) -> int:
        """Get embedding dimensions."""
        return self.DIMENSIONS

    def is_available(self) -> bool:
        """Check if the embedder is available."""
        try:
            self._load_model()
            return True
        except Exception:
            return False

    @staticmethod
    def info() -> dict:
        """Get model information."""
        return {
            "model_name": "BAAI/bge-m3",
            "dimensions": 1024,
            "max_tokens": 8192,
            "query_tokens": 512,
            "languages": "100+ including German",
            "license": "MIT",
            "multilingual": True,
            "library": "FlagEmbedding",
            "singleton_cache": True,
            "default_fp16": True,
        }
