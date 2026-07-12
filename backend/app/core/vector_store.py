"""
Qdrant vector store wrapper.
Handles: collection management, insertion, hybrid search, filter by repo.
"""

import logging
from typing import Optional
from uuid import uuid4

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import ResponseHandlingException

from app.config import settings
from app.models.schemas import CodeChunk, ChunkMetadata
from app.core.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Manages Qdrant collection for code chunk vectors.

    Features:
      - Collection auto-creation with proper config
      - Batch upsert with embeddings
      - Hybrid search (dense + payload filter)
      - Repo-scoped search
      - Deletion by repo name
    """

    def __init__(self, embedding_provider: EmbeddingProvider):
        self.embedder = embedding_provider

        self.client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
            timeout=30,
        )

        self._collection_name = settings.qdrant_collection_name
        self._ensure_collection()

    def _ensure_collection(self):
        """Create the collection if it doesn't exist, with proper schema."""
        collections = self.client.get_collections().collections
        existing = {c.name for c in collections}

        if self._collection_name not in existing:
            logger.info(f"Creating collection '{self._collection_name}'...")
            self.client.create_collection(
                collection_name=self._collection_name,
                vectors_config=qdrant_models.VectorParams(
                    size=self.embedder.dimension,
                    distance=qdrant_models.Distance.COSINE,
                ),
            )

            # Create payload indexes for fast filtering
            keyword_fields = [
                "repo_name", "file_path", "language",
                "symbol_type", "symbol_name", "parent_class",
            ]
            integer_fields = ["start_line", "end_line"]

            for field in keyword_fields:
                self.client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field,
                    field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
                )
            for field in integer_fields:
                self.client.create_payload_index(
                    collection_name=self._collection_name,
                    field_name=field,
                    field_schema=qdrant_models.PayloadSchemaType.INTEGER,
                )

            logger.info(f"Collection '{self._collection_name}' created successfully")
        else:
            logger.debug(f"Collection '{self._collection_name}' exists")

    def index_chunks(
        self, chunks: list[CodeChunk], batch_size: int = 50
    ) -> int:
        """
        Embed and index code chunks into Qdrant.

        Args:
            chunks: List of CodeChunk objects.
            batch_size: Batch size for embedding + upsert.

        Returns:
            Number of points indexed.
        """
        if not chunks:
            return 0

        texts = [c.text for c in chunks]
        logger.info(f"Computing embeddings for {len(texts)} chunks...")
        embeddings = self.embedder.embed_batch(texts, batch_size=batch_size)

        # Build Qdrant points
        points: list[qdrant_models.PointStruct] = []
        for chunk, vector in zip(chunks, embeddings):
            payload = chunk.metadata.model_dump()

            point = qdrant_models.PointStruct(
                id=uuid4().hex,
                vector=vector,
                payload=payload,
            )
            points.append(point)

        # Upsert in batches
        for i in range(0, len(points), batch_size):
            batch = points[i : i + batch_size]
            self.client.upsert(
                collection_name=self._collection_name,
                points=batch,
                wait=True,
            )

        logger.info(f"Indexed {len(points)} chunks in '{self._collection_name}'")
        return len(points)

    def search(
        self,
        query: str,
        repo_name: str | None = None,
        top_k: int = 10,
        score_threshold: float = 0.0,
        language: str | None = None,
        symbol_type: str | None = None,
        file_path: str | None = None,
    ) -> list[tuple[ChunkMetadata, float]]:
        """
        Hybrid search: dense vector similarity + payload filters.

        Args:
            query: Natural language query string.
            repo_name: Filter to specific repo (recommended).
            top_k: Number of results to return.
            score_threshold: Minimum similarity score.
            language: Filter by programming language.
            symbol_type: Filter by symbol type (function, class, etc.).
            file_path: Filter by exact file path.

        Returns:
            List of (ChunkMetadata, score) tuples sorted by relevance.
        """
        query_vector = self.embedder.embed(query)

        # Build filter conditions
        must_conditions: list[qdrant_models.FieldCondition] = []
        if repo_name:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="repo_name",
                    match=qdrant_models.MatchValue(value=repo_name),
                )
            )
        if language:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="language",
                    match=qdrant_models.MatchValue(value=language),
                )
            )
        if symbol_type:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="symbol_type",
                    match=qdrant_models.MatchValue(value=symbol_type),
                )
            )
        if file_path:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="file_path",
                    match=qdrant_models.MatchValue(value=file_path),
                )
            )

        search_filter = qdrant_models.Filter(must=must_conditions) if must_conditions else None

        # Execute search
        results = self.client.search(
            collection_name=self._collection_name,
            query_vector=query_vector,
            query_filter=search_filter,
            limit=top_k,
            score_threshold=score_threshold,
        )

        # Parse results
        parsed: list[tuple[ChunkMetadata, float]] = []
        for res in results:
            metadata = ChunkMetadata(**res.payload)
            parsed.append((metadata, res.score))

        logger.debug(f"Search returned {len(parsed)} results (query: '{query[:50]}')")
        return parsed

    def search_by_symbol_name(
        self,
        symbol_name: str,
        repo_name: str | None = None,
        exact: bool = False,
    ) -> list[ChunkMetadata]:
        """
        Search chunks by symbol name (exact or prefix match).

        Useful for locating specific functions/classes without embedding.
        """
        must_conditions: list[qdrant_models.FieldCondition] = []
        if repo_name:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="repo_name",
                    match=qdrant_models.MatchValue(value=repo_name),
                )
            )

        if exact:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="symbol_name",
                    match=qdrant_models.MatchValue(value=symbol_name),
                )
            )
        else:
            must_conditions.append(
                qdrant_models.FieldCondition(
                    key="symbol_name",
                    match=qdrant_models.MatchText(text=symbol_name),
                )
            )

        search_filter = qdrant_models.Filter(must=must_conditions)

        results = self.client.scroll(
            collection_name=self._collection_name,
            scroll_filter=search_filter,
            limit=50,
        )

        return [ChunkMetadata(**res.payload) for res in results[0]]

    def delete_repo(self, repo_name: str) -> int:
        """
        Delete all chunks for a repository.

        Returns:
            1 if successful, 0 otherwise.
        """
        try:
            self.client.delete(
                collection_name=self._collection_name,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="repo_name",
                                match=qdrant_models.MatchValue(value=repo_name),
                            )
                        ]
                    )
                ),
            )
            logger.info(f"Deleted repo '{repo_name}' from vector store")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete repo {repo_name}: {e}")
            return 0

    def delete_file_chunks(self, repo_name: str, file_path: str) -> int:
        """Delete all chunks belonging to a specific file."""
        try:
            self.client.delete(
                collection_name=self._collection_name,
                points_selector=qdrant_models.FilterSelector(
                    filter=qdrant_models.Filter(
                        must=[
                            qdrant_models.FieldCondition(
                                key="repo_name",
                                match=qdrant_models.MatchValue(value=repo_name),
                            ),
                            qdrant_models.FieldCondition(
                                key="file_path",
                                match=qdrant_models.MatchValue(value=file_path),
                            )
                        ]
                    )
                ),
            )
            logger.debug(f"Deleted old chunks for {file_path} in repo {repo_name}")
            return 1
        except Exception as e:
            logger.error(f"Failed to delete file {file_path} in {repo_name}: {e}")
            return 0

    def count_chunks(self, repo_name: str | None = None) -> int:
        """Count chunks, optionally filtered by repo."""
        if repo_name:
            result = self.client.count(
                collection_name=self._collection_name,
                count_filter=qdrant_models.Filter(
                    must=[
                        qdrant_models.FieldCondition(
                            key="repo_name",
                            match=qdrant_models.MatchValue(value=repo_name),
                        )
                    ]
                ),
            )
            return result.count
        else:
            result = self.client.count(
                collection_name=self._collection_name
            )
            return result.count

    def health(self) -> bool:
        """Check if Qdrant is reachable."""
        try:
            self.client.get_collections()
            return True
        except Exception:
            return False