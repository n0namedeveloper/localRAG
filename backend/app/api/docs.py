"""Documentation Generation API endpoint."""

import logging
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.config import DATA_DIR
from app.core.llm_client import get_llm_client

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/docs", tags=["docs"])

class DocRequest(BaseModel):
    repo_name: str
    file_path: str

@router.post("/generate")
async def generate_docs(request: DocRequest):
    """
    Generate comprehensive Markdown documentation for a specific file in a repository.
    """
    try:
        # Sanitize paths to prevent directory traversal
        clean_repo_name = os.path.basename(request.repo_name)
        file_path_clean = request.file_path.lstrip("/")
        
        full_path = DATA_DIR / clean_repo_name / file_path_clean
        
        if not full_path.exists() or not full_path.is_file():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path_clean}")
            
        content = full_path.read_text(encoding="utf-8", errors="ignore")
        
        prompt = f"""You are an expert technical writer and senior developer.
Please write comprehensive Markdown documentation for the following source code file: `{file_path_clean}`.
Include:
1. High-level overview of what this file does.
2. Dependencies and architecture.
3. Detailed explanation of the main classes, functions, and their parameters/return types.
4. An example of how to use this module (if applicable).

Here is the source code:
```
{content}
```
"""

        llm = get_llm_client()

        async def generate():
            async for chunk in llm.chat_stream(
                messages=[{"role": "user", "content": prompt}],
                system_prompt="You are an expert AI documentation generator. Produce clear, professional markdown.",
            ):
                yield chunk

        return StreamingResponse(generate(), media_type="text/event-stream")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Docs generation error")
        raise HTTPException(status_code=500, detail=str(e))
