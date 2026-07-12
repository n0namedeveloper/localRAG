"""
Main FastAPI application entrypoint.

This file:
  - Initializes all components via lifespan (vector store, LLM, graph, etc.)
  - Stores singletons in app.state for proper dependency injection
  - Registers all API routes
  - Starts the FastAPI app
"""

import logging
import sys
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.vector_store import VectorStore
from app.core.llm_client import DeepSeekClient
from app.core.embedding import EmbeddingProvider
from app.core.rag_engine import RAGEngine
from app.ingestion.graph_builder import DependencyGraph
from app.ingestion.pipeline import IngestionPipeline
from app.ingestion.repo_manager import RepoManager
from app.api.chat import router as chat_router
from app.api.repo import router as repo_router
from app.api.search import router as search_router
from app.api.health import router as health_router
from app.api.graph import router as graph_router
from app.api.logs import router as logs_router, SSELoggingHandler
from app.api.settings import router as settings_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# Route ingestion logs to the SSE stream
ingestion_logger = logging.getLogger("app.ingestion")
ingestion_logger.setLevel(logging.INFO)
sse_handler = SSELoggingHandler()
sse_handler.setFormatter(logging.Formatter("%(message)s"))
ingestion_logger.addHandler(sse_handler)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down all application-level singletons."""
    logger.info("Starting CodeRAG API...")

    embedding_provider = EmbeddingProvider()
    vector_store = VectorStore(embedding_provider=embedding_provider)
    dep_graph = DependencyGraph()
    pipeline = IngestionPipeline(vector_store=vector_store, dep_graph=dep_graph)
    rag_engine = RAGEngine(
        vector_store=vector_store,
        dep_graph=dep_graph,
    )
    repo_manager = RepoManager()

    app.state.vector_store = vector_store
    app.state.pipeline = pipeline
    app.state.rag_engine = rag_engine
    app.state.repo_manager = repo_manager

    logger.info("All components initialized")
    yield

    logger.info("Shutting down CodeRAG API...")


app = FastAPI(
    title="CodeRAG API",
    description="Chat with your GitHub repositories using RAG and code-aware context.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from app.api.agent import router as agent_router

app.include_router(chat_router)
app.include_router(repo_router)
app.include_router(search_router)
app.include_router(settings_router)
app.include_router(agent_router)
app.include_router(health_router)
app.include_router(graph_router)
app.include_router(logs_router)


@app.get("/")
async def root():
    return {
        "message": "Welcome to CodeRAG API",
        "docs": "/docs",
        "health": "/api/health",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info" if settings.debug else "warning",
    )