"""Repository management API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models.schemas import RepoCloneRequest, RepoStatusResponse
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.repo_manager import RepoManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["repo"])


def get_pipeline(request: Request) -> IngestionPipeline:
    """Dependency: retrieve ingestion pipeline from app.state."""
    pipeline = getattr(request.app.state, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    return pipeline


def get_repo_manager(request: Request) -> RepoManager:
    """Dependency: retrieve repo manager from app.state."""
    manager = getattr(request.app.state, "repo_manager", None)
    if manager is None:
        raise HTTPException(status_code=503, detail="RepoManager not initialized")
    return manager


@router.post("/clone", response_model=RepoStatusResponse)
async def clone_repo(
    request: RepoCloneRequest,
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """
    Clone or update a repository and start indexing.

    Body:
        {
            "repo_url": "https://github.com/user/repo",
            "branch": "main",
            "force_reindex": false
        }
    """
    try:
        effective_branch = request.branch if request.branch and request.branch.strip() else None
        result = pipeline.run(
            repo_url=request.repo_url,
            branch=effective_branch,
            force_reindex=request.force_reindex,
        )
        return RepoStatusResponse(
            repo_url=request.repo_url,
            repo_name=result["repo_name"],
            status=result["status"],
            files_indexed=result.get("files_parsed", 0),
            symbols_indexed=result.get("symbols_count", 0),
            last_indexed=None,
            error_message=result.get("error"),
        )
    except Exception as e:
        logger.exception("Clone error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{repo_url}", response_model=RepoStatusResponse)
async def get_repo_status(
    repo_url: str,
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """Get the current indexing status of a repository."""
    try:
        status_enum = pipeline.get_repo_status(repo_url)
        stats = pipeline.get_index_stats(repo_url)
        return RepoStatusResponse(
            repo_url=repo_url,
            repo_name=stats.get("repo_name", "unknown"),
            status=status_enum,
            files_indexed=stats.get("files_parsed", 0),
            symbols_indexed=stats.get("symbols_count", 0),
            last_indexed=None,
            error_message=None,
        )
    except Exception as e:
        logger.exception("Status error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_repos(
    repo_manager: RepoManager = Depends(get_repo_manager),
):
    """List all cloned repositories."""
    try:
        repos_dir = repo_manager.settings.repos_dir
        repos = [
            item.name
            for item in repos_dir.iterdir()
            if item.is_dir()
        ] if repos_dir.exists() else []
        return {"repos": repos}
    except Exception as e:
        logger.exception("List repos error")
        raise HTTPException(status_code=500, detail=str(e))
