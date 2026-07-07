"""
Embedding provider.
Supports: BGE-M3 (local via sentence-transformers), OpenAI text-embedding-3-small.
"""

import logging
from typing import Optional

import numpy as np

from app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider:
    """
    Wrapper around embedding models for code chunks.

    Usage:
        provider = EmbeddingProvider()
        vec = provider.embed("def hello(): pass")
        vecs = provider.embed_batch(["chunk1", "chunk2"])
    """

    def __init__(self):
        self._model = None
        self._provider_name: str | None = None
        self._dimension: int = settings.embedding_dimension
        self._init_model()

    def _init_model(self):
        """Initialize the embedding model based on config."""
        provider = settings.embedding_provider.lower()

        if provider == "openai":
            self._init_openai()
        elif provider == "bge-m3":
            self._init_bge_m3()
        else:
            logger.warning(
                f"Unknown embedding provider '{provider}', falling back to BGE-M3"
            )
            self._init_bge_m3()

    def _init_openai(self):
        """Initialize OpenAI embedding client."""
        try:
            import openai

            self._client = openai.OpenAI(api_key=settings.openai_api_key)
            self._model_name = "text-embedding-3-small"
            self._provider_name = "openai"
            self._dimension = 1536
            logger.info("OpenAI embedding initialized: text-embedding-3-small")
        except Exception as e:
            logger.error(f"Failed to init OpenAI embeddings: {e}")
            raise

    def _init_bge_m3(self):
        """Initialize local BGE-M3 model via sentence-transformers."""
        try:
            from sentence_transformers import SentenceTransformer

            model_name = settings.local_embedding_model
            logger.info(f"Loading local embedding model: {model_name}...")
            self._model = SentenceTransformer(
                model_name, trust_remote_code=True
            )
            self._provider_name = "bge-m3"
            # BGE-M3 outputs 1024-dim vectors
            self._dimension = self._model.get_sentence_embedding_dimension()
            logger.info(
                f"Local embedding model loaded: {model_name} "
                f"(dim={self._dimension})"
            )
        except Exception as e:
            logger.error(f"Failed to load local embedding model: {e}")
            raise

    def embed(self, text: str) -> list[float]:
        """
        Embed a single text string.

        Args:
            text: Text to embed (code chunk text).

        Returns:
            Dense vector as list of floats.
        """
        if self._provider_name == "openai":
            return self._embed_openai([text])[0]

        # Local model
        vec = self._model.encode(text, normalize_embeddings=True)
        return vec.tolist()

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[list[float]]:
        """
        Embed a batch of texts, handling both providers.

        Args:
            texts: List of text strings to embed.
            batch_size: Batch size for local model inference.

        Returns:
            List of dense vectors.
        """
        if not texts:
            return []

        if self._provider_name == "openai":
            # OpenAI has its own batching
            return self._embed_openai(texts)

        # Local model
        all_embeddings = self._model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return all_embeddings.tolist()

    def _embed_openai(self, texts: list[str]) -> list[list[float]]:
        """Embed via OpenAI API with retries."""
        try:
            response = self._client.embeddings.create(
                input=texts,
                model=self._model_name,
            )
            # Sort by index to preserve order
            sorted_data = sorted(response.data, key=lambda x: x.index)
            return [item.embedding for item in sorted_data]
        except Exception as e:
            logger.error(f"OpenAI embedding failed: {e}")
            raise

    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension

    def get_text_hash(self, text: str) -> str:
        """Simple hash for caching deduplication."""
        import hashlib
        return hashlib.md5(text.encode()).hexdigest()

    def compute_similarity(
        self, vec_a: list[float], vec_b: list[float]
    ) -> float:
        """Cosine similarity between two vectors."""
        a = np.array(vec_a, dtype=np.float32)
        b = np.array(vec_b, dtype=np.float32)
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))