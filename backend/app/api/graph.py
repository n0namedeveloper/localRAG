"""Graph API routes: export dependency graph for frontend visualization."""
import json
import logging
from pathlib import Path

from fastapi import APIRouter, HTTPException

from app.models.schemas import GraphDataResponse
from app.config import INDEX_DIR

router = APIRouter(prefix="/graph", tags=["graph"])
logger = logging.getLogger(__name__)


@router.get("/{repo_name}", response_model=GraphDataResponse)
def get_graph(repo_name: str):
    """Export dependency graph for a given repo."""
    graph_file = INDEX_DIR / repo_name / "graph.json"
    if not graph_file.exists():
        # Attempt to reconstruct from qdrant symbols (best-effort)
        raise HTTPException(
            status_code=404,
            detail=f"Graph file not found for repo: '{repo_name}'. Run indexing first.",
        )
    with open(graph_file, "r", encoding="utf-8") as f:
        payload = json.load(f)
    return GraphDataResponse(**payload)