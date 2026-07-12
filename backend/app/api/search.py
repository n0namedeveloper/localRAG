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
    try:
        repo_name: str | None = None
        if request.repo_url and request.repo_url.lower() != "all":
            repo_name = request.repo_url.rstrip("/").rstrip(".git").split("/")[-1] or None
            
        if request.exact_match:
            # Exact match by symbol name
            chunks = vector_store.search_by_symbol_name(
                symbol_name=request.query,
                repo_name=repo_name,
                exact=False
            )
            return [SearchResult(metadata=m, score=1.0) for m in chunks[:request.top_k]]
        else:
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

from fastapi.responses import StreamingResponse

class SummaryRequest(SearchRequest):
    pass

@router.post("/summary")
async def search_summary(
    request: SummaryRequest,
    vector_store: VectorStore = Depends(get_vector_store),
):
    """Generate an AI summary for the search results."""
    try:
        repo_name: str | None = None
        if request.repo_url and request.repo_url.lower() != "all":
            repo_name = request.repo_url.rstrip("/").rstrip(".git").split("/")[-1] or None

        if request.exact_match:
            chunks_meta = vector_store.search_by_symbol_name(request.query, repo_name, exact=False)[:5]
        else:
            results = vector_store.search(request.query, repo_name, top_k=5)
            chunks_meta = [m for m, _ in results]

        if not chunks_meta:
            async def empty_stream():
                yield "No results found to summarize."
            return StreamingResponse(empty_stream(), media_type="text/event-stream")

        prompt = "Summarize the following code snippets based on the user query: " + request.query + "\n\n"
        for i, meta in enumerate(chunks_meta):
            prompt += f"--- Snippet {i+1} ({meta.file_path} - {meta.symbol_name}) ---\n"
            prompt += meta.signature + "\n\n"

        from app.core.llm_client import get_llm_client
        llm = get_llm_client()

        async def generate():
            async for chunk in llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are a helpful AI assistant summarizing search results for a codebase. Be extremely concise. Use markdown.",
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logger.exception("Summary error")
        raise HTTPException(status_code=500, detail=str(e))
