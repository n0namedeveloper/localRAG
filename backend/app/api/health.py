"""Health check API endpoint."""

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.vector_store import VectorStore
from app.core.llm_client import DeepSeekClient

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/health", tags=["health"])


class HealthResponse(BaseModel):
    status: str
    services: dict


def get_vector_store() -> VectorStore:
    """Dependency injection for vector store."""
    store = getattr(get_vector_store, "store", None)
    if store is None:
        raise HTTPException(status_code=503, detail="Vector store not initialized")
    return store


def get_llm_client() -> DeepSeekClient:
    """Dependency injection for LLM client."""
    client = getattr(get_llm_client, "client", None)
    if client is None:
        raise HTTPException(status_code=503, detail="LLM client not initialized")
    return client


@router.get("", response_model=HealthResponse)
async def health_check(
    vector_store: VectorStore = Depends(get_vector_store),
    llm_client: DeepSeekClient = Depends(get_llm_client),
):
    """
    Check health of all services.

    Returns:
        {
            "status": "healthy|unhealthy",
            "services": {
                "vector_store": "healthy|unhealthy",
                "llm": "healthy|unhealthy"
            }
        }
    """
    services = {
        "vector_store": "unhealthy",
        "llm": "unhealthy",
    }

    # Check vector store
    try:
        if vector_store and vector_store.health():
            services["vector_store"] = "healthy"
        else:
            services["vector_store"] = "unhealthy"
    except Exception as e:
        logger.error(f"Vector store health check failed: {e}")
        services["vector_store"] = "unhealthy"

    # Check LLM
    try:
        if llm_client:
            # Simple ping by checking if client is initialized
            services["llm"] = "healthy"
        else:
            services["llm"] = "unhealthy"
    except Exception as e:
        logger.error(f"LLM health check failed: {e}")
        services["llm"] = "unhealthy"

    # Overall status
    status = "healthy" if all(v == "healthy" for v in services.values()) else "unhealthy"

    return HealthResponse(status=status, services=services)