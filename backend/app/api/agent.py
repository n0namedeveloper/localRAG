"""Agent API endpoint — code generation and planning."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.models.schemas import ChatRequest
from app.core.vector_store import VectorStore
from app.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/agent", tags=["agent"])

def get_vector_store(request: Request) -> VectorStore:
    store = getattr(request.app.state, "vector_store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    return store

@router.post("/plan")
async def generate_plan(
    request: ChatRequest,
    vector_store: VectorStore = Depends(get_vector_store),
):
    """
    Generate an implementation plan for an issue based on repo context.
    """
    try:
        repo_name: str | None = None
        if request.repo_url and request.repo_url.lower() != "all":
            repo_name = request.repo_url.rstrip("/").rstrip(".git").split("/")[-1] or None

        # Gather context
        results = vector_store.search(
            query=request.question,
            repo_name=repo_name,
            top_k=20,
        )

        context_text = ""
        for metadata, score in results:
            context_text += f"--- {metadata.file_path} (Symbol: {metadata.symbol_name}) ---\n"
            context_text += metadata.signature + "\n\n"

        prompt = f"""You are a senior software engineer. The user wants to implement the following issue/feature:
{request.question}

Here is some context from the codebase that might be relevant:
{context_text}

Analyze the context and write a detailed implementation plan.
Break it down into:
1. Architecture/Design approach
2. Files to create/modify
3. Step-by-step instructions
Be specific and reference the actual symbols and file paths provided. Use markdown.
"""

        llm = get_llm_client()

        async def generate():
            async for chunk in llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are an expert AI coding agent. Produce a clear and actionable implementation plan.",
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/event-stream")
    except Exception as e:
        logger.exception("Agent plan error")
        raise HTTPException(status_code=500, detail=str(e))
