"""Health check API endpoint."""

import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.core.vector_store import VectorStore
from app.core.llm_client import DeepSeekClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    services: dict


@router.get("", response_model=HealthResponse)
async def health_check(request: Request):
    """
    Check health of all services.

    Returns:
        {
            "status": "healthy|degraded",
            "services": {
                "vector_store": "healthy|unhealthy",
                "llm": "configured|unconfigured"
            }
        }
    """
    services: dict[str, str] = {}

    vector_store: VectorStore | None = getattr(request.app.state, "vector_store", None)
    try:
        services["vector_store"] = "healthy" if vector_store and vector_store.health() else "unhealthy"
    except Exception:
        logger.error("Vector store health check failed", exc_info=True)
        services["vector_store"] = "unhealthy"

    llm_client: DeepSeekClient | None = getattr(request.app.state, "llm_client", None)
    services["llm"] = "configured" if llm_client and llm_client.api_key else "unconfigured"

    status = "healthy" if all(v not in ("unhealthy", "unconfigured") for v in services.values()) else "degraded"
    return HealthResponse(status=status, services=services)
