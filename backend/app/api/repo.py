"""Repository management API endpoints."""

import logging
import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, BackgroundTasks
from fastapi.responses import JSONResponse

from app.models.schemas import (
    RepoCloneRequest,
    RepoStatusResponse,
    RepoListResponse,
    RepoStatsResponse,
    RepoStatus,
)
from app.config import INDEX_DIR
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.repo_manager import RepoManager, repo_url_to_name
from app.api.logs import put_log

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/repo", tags=["repo"])


# ── Dependencies ────────────────────────────────────────────────────────────

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


# ── Background worker ───────────────────────────────────────────────────────

def _run_ingestion(pipeline: IngestionPipeline, repo_url: str, branch: str | None, force_reindex: bool):
    """Synchronous function run in a background thread by FastAPI BackgroundTasks."""
    try:
        result = pipeline.run(
            repo_url=repo_url,
            branch=branch,
            force_reindex=force_reindex,
        )
        logger.info(f"Background ingestion finished: {result.get('repo_name')} — {result.get('status')}")
    except Exception as e:
        logger.exception(f"Background ingestion failed for {repo_url}: {e}")


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/clone", status_code=202)
async def clone_repo(
    request: RepoCloneRequest,
    background_tasks: BackgroundTasks,
    pipeline: IngestionPipeline = Depends(get_pipeline),
):
    """
    Clone or update a repository and start indexing (non-blocking).

    Returns 202 immediately. Poll /api/repo/stats/{repo_name} to check progress.
    """
    repo_name = repo_url_to_name(request.repo_url)
    effective_branch = request.branch if request.branch and request.branch.strip() else None

    # Fire-and-forget: ingestion runs in a background thread
    background_tasks.add_task(
        _run_ingestion,
        pipeline,
        request.repo_url,
        effective_branch,
        request.force_reindex,
    )

    await put_log({
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "level": "INFO",
        "message": f"Queued ingestion for: {request.repo_url}",
        "repo_name": repo_name,
        "stage": "queued",
    })

    return {
        "repo_name": repo_name,
        "repo_url": request.repo_url,
        "status": "indexing",
        "message": "Ingestion started in background. Poll /api/repo/stats/{repo_name} for progress.",
    }


@router.get("/list", response_model=RepoListResponse)
async def list_repos():
    """List all indexed repositories with detailed statistics."""
    repos: list[RepoStatsResponse] = []

    if not INDEX_DIR.exists():
        return RepoListResponse(repos=[])

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


@router.get("/stats/{repo_name}", response_model=RepoStatsResponse)
async def get_repo_stats(repo_name: str):
    """Get detailed statistics for a specific repository."""
    repo_dir = INDEX_DIR / repo_name
    meta_file = repo_dir / "meta.json"
    graph_file = repo_dir / "graph.json"

    if not repo_dir.exists():
        raise HTTPException(status_code=404, detail=f"Repository '{repo_name}' not found")

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
        except Exception:
            pass

    return RepoStatsResponse(
        repo_name=repo_name,
        status="ready" if meta_file.exists() else "indexing",
        files_parsed=files_parsed,
        symbols_count=symbols_count,
        chunks_count=chunks_count,
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        last_indexed=last_indexed,
        languages=languages,
    )


@router.get("/{repo_name}", response_model=RepoStatusResponse)
async def get_repo_status(repo_name: str):
    """Get status for a specific repository."""
    repo_dir = INDEX_DIR / repo_name
    meta_file = repo_dir / "meta.json"

    if not repo_dir.exists():
        return RepoStatusResponse(
            repo_url="",
            repo_name=repo_name,
            status=RepoStatus.NOT_FOUND,
            files_indexed=0,
            symbols_indexed=0,
            last_indexed=None,
            error_message="Repository not found",
        )

    files_parsed = 0
    symbols_count = 0
    last_indexed = None

    if meta_file.exists():
        try:
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
            files_parsed = meta.get("files_parsed", 0)
            symbols_count = meta.get("symbols_count", 0)
            last_idx_str = meta.get("last_indexed")
            if last_idx_str:
                try:
                    last_indexed = datetime.fromisoformat(last_idx_str)
                except Exception:
                    pass
        except Exception:
            pass

    return RepoStatusResponse(
        repo_url="",
        repo_name=repo_name,
        status=RepoStatus.READY if meta_file.exists() else RepoStatus.NOT_FOUND,
        files_indexed=files_parsed,
        symbols_indexed=symbols_count,
        last_indexed=last_indexed,
    )