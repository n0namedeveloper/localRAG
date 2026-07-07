"""Chat API endpoint — core RAG functionality with streaming support."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse

from app.models.schemas import ChatRequest, ChatResponse
from app.core.rag_engine import RAGEngine

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


def get_rag_engine() -> RAGEngine:
    """Dependency injection for RAG engine (set at startup)."""
    engine = getattr(get_rag_engine, "engine", None)
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
            "max_chunks": 15,
            "stream": false
        }
    """
    try:
        response = engine.answer(request)
        return response
    except Exception as e:
        logger.exception(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    engine: RAGEngine = Depends(get_rag_engine),
):
    """
    Streaming chat via Server-Sent Events.

    Returns SSE events:
      - event: "token", data: "text chunk"
      - event: "sources", data: JSON with sources array
      - event: "done", data: "true"
    """
    async def event_generator():
        full_answer = ""
        try:
            async for token in engine.answer_stream(request):
                full_answer += token
                yield {
                    "event": "token",
                    "data": token,
                }

            # After streaming completes, parse sources from the last yield
            # (sources are embedded in the final token as HTML comment)
            # For simplicity, we regenerate sources here
            sources = engine._extract_sources(
                full_answer,
                engine._retrieve_chunks(
                    query=request.question,
                    repo_url=request.repo_url,
                    top_k=request.max_chunks,
                ),
            )
            repo_name = engine._extract_repo_name(request.repo_url)
            for source in sources:
                source.github_url = engine._build_github_url(
                    request.repo_url, source.file_path, source.start_line
                )

            yield {
                "event": "sources",
                "data": json.dumps(
                    [s.model_dump() for s in sources], default=str
                ),
            }
            yield {"event": "done", "data": "true"}

        except Exception as e:
            logger.exception(f"Stream error: {e}")
            yield {
                "event": "error",
                "data": json.dumps({"error": str(e)}),
            }

    return EventSourceResponse(event_generator())