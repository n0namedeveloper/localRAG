"""Chat API endpoint — core RAG functionality with streaming support."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest, ChatResponse, SourceReference
from app.core.rag_engine import RAGEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_rag_engine(request: Request) -> RAGEngine:
    """Dependency: retrieve RAG engine from app.state."""
    engine = getattr(request.app.state, "rag_engine", None)
    if engine is None:
        raise HTTPException(status_code=503, detail="RAG Engine not initialized")
    return engine


@router.post("", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    engine: RAGEngine = Depends(get_rag_engine),
):
    """
    Synchronous chat: answer a question about a repository.

    Body:
        {
            "repo_url": "https://github.com/user/repo",
            "question": "How does authorization work?",
            "max_chunks": 15
        }
    """
    try:
        return engine.answer(request)
    except Exception as e:
        logger.exception("Chat error")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    engine: RAGEngine = Depends(get_rag_engine),
):
    """
    Streaming chat via Server-Sent Events.

    SSE events:
      - event data: {"event": "token",   "data": "text chunk"}
      - event data: {"event": "sources",  "data": [...]}
      - event data: {"event": "done",     "data": "true"}
      - event data: {"event": "error",    "data": {"error": "..."}}
    """
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            async for item in engine.answer_stream(request):
                if isinstance(item, str):
                    payload = json.dumps(
                        {"event": "token", "data": item}, ensure_ascii=False
                    )
                    yield f"data: {payload}\n\n"
                elif isinstance(item, list):
                    # Final item: list[SourceReference]
                    sources: list[SourceReference] = item
                    payload = json.dumps(
                        {"event": "sources", "data": [s.model_dump() for s in sources]},
                        ensure_ascii=False,
                    )
                    yield f"data: {payload}\n\n"

            payload = json.dumps({"event": "done", "data": "true"}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        except Exception as e:
            logger.exception("Stream error")
            payload = json.dumps(
                {"event": "error", "data": {"error": str(e)}}, ensure_ascii=False
            )
            yield f"data: {payload}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")
