"""Repository management API endpoints."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.models.schemas import RepoCloneRequest, RepoStatusResponse
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.repo_manager import RepoManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["repo"])


def get_pipeline() -> IngestionPipeline:
    """Dependency injection for ingestion pipeline."""
    pipeline = getattr(get_pipeline, "pipeline", None)
    if pipeline is None:
        raise HTTPException(status_code=503, detail="Pipeline not initialized")
    return pipeline


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
        result = pipeline.run(
            repo_url=request.repo_url,
            branch=request.branch,
            force_reindex=request.force_reindex,
        )
        return RepoStatusResponse(
            repo_url=request.repo_url,
            repo_name=result["repo_name"],
            status=result["status"],
            files_indexed=result.get("files_parsed", 0),
            symbols_indexed=result.get("symbols_count", 0),
            last_indexed=None,  # Not exposed in this simplified version
            error_message=result.get("error"),
        )
    except Exception as e:
        logger.exception(f"Clone error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{repo_url}", response_model=RepoStatusResponse)
async def get_repo_status(
    repo_url: str,
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """
    Get the current indexing status of a repository.

    Returns:
        RepoStatusResponse with status and stats.
    """
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
        logger.exception(f"Status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_repos(
    repo_manager: RepoManager = Depends(lambda: RepoManager()),
):
    """
    List all cloned repositories.

    Returns:
        List of repo names.
    """
    try:
        # Just list directories in repos dir
        repos_dir = repo_manager.settings.repos_dir
        repos = []
        if repos_dir.exists():
            for item in repos_dir.iterdir():
                if item.is_dir():
                    repos.append(item.name)
        return {"repos": repos}
    except Exception as e:
        logger.exception(f"List repos error: {e}")
        raise HTTPException(status_code=500, detail=str(e))