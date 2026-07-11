"""Repository management API endpoints."""

import logging
import json
import time
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse

from app.models.schemas import (
    RepoCloneRequest,
    RepoStatusResponse,
    RepoListResponse,
    RepoStatsResponse,
    LogEntry,
)
from app.config import INDEX_DIR
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.repo_manager import RepoManager
from app.api.logs import put_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["repo"])
pipeline = IngestionPipeline()


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
        await put_log({
            "timestamp": datetime.utcnow().isoformat(),
            "level": "INFO",
            "message": f"Cloning repository: {request.repo_url}",
            "repo_name": result["repo_name"],
            "stage": "cloning",
        })
        return RepoStatusResponse(
            repo_url=request.repo_url,
            repo_name=result["repo_name"],
            status=result["status"],
            files_parsed=result.get("files_parsed", 0),
            symbols_count=result.get("symbols_count", 0),
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
            files_parsed=stats.get("files_parsed", 0),
            symbols_count=stats.get("symbols_count", 0),
            last_indexed=None,
            error_message=None,
        )
    except Exception as e:
        logger.exception("Status error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list", response_model=RepoListResponse)
async def list_repos():
    """List all indexed repositories with detailed statistics."""
    repos: list[RepoStatsResponse] = []
    for idx_dir in INDEX_DIR.iterdir():
        if not idx_dir.is_dir():
            continue
        meta_file = idx_dir / "meta.json"
        graph_file = idx_dir / "graph.json"
        repo_name = idx_dir.name
        status = "ready" if meta_file.exists() else "indexing"

        files_parsed = 0
        symbols_count = 0
        chunks_count = 0
        graph_nodes = 0
        graph_edges = 0
        last_indexed = None
        languages: dict[str, int] = {}

        if meta_file.exists():
            try:
                with open(meta_file, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                files_parsed = meta.get("files_parsed", 0)
                symbols_count = meta.get("symbols_count", 0)
                chunks_count = meta.get("chunks_count", 0)
                last_idx_str = meta.get("last_indexed")
                if last_idx_str:
                    from datetime import datetime
                    try:
                        last_indexed = datetime.fromisoformat(last_idx_str)
                    except Exception:
                        pass
                languages = meta.get("languages", {})
            except Exception:
                pass

        if graph_file.exists():
            try:
                with open(graph_file, "r", encoding="utf-8") as f:
                    g = json.load(f)
                graph_nodes = len(g.get("nodes", []))
                graph_edges = len(g.get("edges", []))
                status = "ready"
            except Exception:
                pass

        repos.append(
            RepoStatsResponse(
                repo_name=repo_name,
                status=status,
                files_parsed=files_parsed,
                symbols_count=symbols_count,
                chunks_count=chunks_count,
                graph_nodes=graph_nodes,
                graph_edges=graph_edges,
                last_indexed=last_indexed,
                languages=languages,
            )
        )
    return RepoListResponse(repos=repos)


@router.get("/{repo_name}", response_model=RepoStatusResponse)
async def get_repo_status(
    repo_name: str,
):
    """Get detailed statistics for a specific repository."""
    repo_dir = INDEX_DIR / repo_name
    meta_file = repo_dir / "meta.json"

    if not repo_dir.exists():
        return RepoStatusResponse(
            repo_url="",
            repo_name=repo_name,
            status=RepoStatus.NOT_FOUND,
            files_parsed=0,
            symbols_count=0,
            last_indexed=None,
            error_message="Repository not found",
        )

    files_parsed = 0
    symbols_count = 0
    chunks_count = 0
    graph_nodes = 0
    graph_edges = 0
    last_indexed = None
    languages: dict[str, int] = {}

    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            files_parsed = meta.get("files_parsed", 0)
            symbols_count = meta.get("symbols_count", 0)
            chunks_count = meta.get("chunks_count", 0)
            last_idx_str = meta.get("last_indexed")
            if last_idx_str:
                from datetime import datetime
                try:
                    last_indexed = datetime.fromisoformat(last_idx_str)
                except Exception:
                    pass
            languages = meta.get("languages", {})
        except Exception:
            pass

    return RepoStatusResponse(
        repo_url="",
        repo_name=repo_name,
        status=RepoStatus.READY if meta_file.exists() else RepoStatus.NOT_FOUND,
        files_parsed=files_parsed,
        symbols_count=symbols_count,
        chunks_count=chunks_count,
        last_indexed=last_indexed,
    )