"""Chat API endpoint — core RAG functionality with streaming support."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

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
    async def event_generator() -> AsyncGenerator[str, None]:
        full_answer = ""
        try:
            async for token in engine.answer_stream(request):
                full_answer += token
                payload = json.dumps({"event": "token", "data": token}, ensure_ascii=False)
                yield f"data: {payload}\n\n"

            # After streaming completes, regenerate sources
            sources = engine._extract_sources(
                full_answer,
                engine._retrieve_chunks(
                    query=request.question,
                    repo_url=request.repo_url,
                    top_k=request.max_chunks,
                ),
            )
            for source in sources:
                source.github_url = engine._build_github_url(
                    request.repo_url, source.file_path, source.start_line
                )

            payload = json.dumps(
                {"event": "sources", "data": [s.model_dump() for s in sources]},
                ensure_ascii=False,
            )
            yield f"data: {payload}\n\n"

            payload = json.dumps({"event": "done", "data": "true"}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

        except Exception as e:
            logger.exception(f"Stream error: {e}")
            payload = json.dumps({"event": "error", "data": {"error": str(e)}}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )
