"""Search API endpoint — direct vector search without RAG."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from typing import List

from app.models.schemas import SearchRequest, SearchResult, ChunkMetadata
from app.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def get_vector_store() -> VectorStore:
    """Dependency injection for vector store."""
    store = getattr(get_vector_store, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    return store


@router.post("", response_model=List[SearchResult])
async def search(
    request: SearchRequest,
    vector_store: VectorStore = Depends(get_vector_store),
):
    """
    Perform a raw vector search in Qdrant.

    Body:
        {
            "repo_url": "https://github.com/user/repo",
            "query": "authorization function",
            "top_k": 10,
            "language": "python",
            "symbol_type": "function"
        }
    """
    try:
        repo_name = request.repo_url.split("/")[-1].replace(".git", "")
        if "@" in repo_name:
            repo_name = repo_name.split("@")[0]

        results = vector_store.search(
            query=request.query,
            repo_name=repo_name,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            language=request.language,
            symbol_type=request.symbol_type,
        )

        # Convert to SearchResult format
        search_results = []
        for metadata, score in results:
            search_results.append(SearchResult(
                metadata=metadata,
                score=score,
            ))

        return search_results
    except Exception as e:
        logger.exception(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=str(e))