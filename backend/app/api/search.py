"""Search API endpoint — direct vector search without RAG."""

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.schemas import SearchRequest, SearchResult
from app.core.vector_store import VectorStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/search", tags=["search"])


def get_vector_store(request: Request) -> VectorStore:
    """Dependency: retrieve vector store from app.state."""
    store = getattr(request.app.state, "vector_store", None)
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
        # Extract bare repo name from URL for filtering
        repo_name = request.repo_url.rstrip("/").rstrip(".git").split("/")[-1]
        results = vector_store.search(
            query=request.query,
            repo_name=repo_name,
            top_k=request.top_k,
            score_threshold=request.score_threshold,
            language=request.language,
            symbol_type=request.symbol_type,
        )
        return [
            SearchResult(metadata=metadata, score=score)
            for metadata, score in results
        ]
    except Exception as e:
        logger.exception("Search error")
        raise HTTPException(status_code=500, detail=str(e))
