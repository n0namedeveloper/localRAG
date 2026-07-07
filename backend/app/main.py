"""
Main FastAPI application entrypoint.

This file:
  - Initializes all components (vector store, LLM, graph, etc.)
  - Sets up dependency injection
  - Registers all API routes
  - Starts the FastAPI app
"""

import logging
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.vector_store import VectorStore
from app.core.llm_client import DeepSeekClient
from app.core.embedding import EmbeddingProvider
from app.core.rag_engine import RAGEngine
from app.ingestion.graph_builder import DependencyGraph
from app.ingestion.pipeline import IngestionPipeline
from app.api.chat import router as chat_router
from app.api.repo import router as repo_router
from app.api.search import router as search_router
from app.api.health import router as health_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Initialize global components
vector_store = VectorStore()
embedding_provider = EmbeddingProvider()
dep_graph = DependencyGraph()
llm_client = DeepSeekClient()

# Initialize ingestion pipeline
pipeline = IngestionPipeline(
    vector_store=vector_store,
    dep_graph=dep_graph,
)

# Set components in globals for dependency injection
# (This is a simplified approach; in production, use DI containers)
setattr(chat_router, "get_rag_engine", lambda: None)
setattr(chat_router.get_rag_engine, "engine", None)

setattr(repo_router, "get_pipeline", lambda: None)
setattr(repo_router.get_pipeline, "pipeline", pipeline)

setattr(search_router, "get_vector_store", lambda: None)
setattr(search_router.get_vector_store, "store", vector_store)

# Create FastAPI app
app = FastAPI(
    title="CodeRAG API",
    description="Chat with your GitHub repositories using RAG and code-aware context.",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(chat_router)
app.include_router(repo_router)
app.include_router(search_router)
app.include_router(health_router)

# Set up dependency injection for RAG engine
def setup_dependencies():
    """Set up global dependencies for API routes."""
    # Inject engine into chat router
    setattr(chat_router.get_rag_engine, "engine", RAGEngine(
        vector_store=vector_store,
        llm_client=llm_client,
        dep_graph=dep_graph,
    ))
    
    # Inject pipeline into repo router
    setattr(repo_router.get_pipeline, "pipeline", pipeline)
    
    # Inject vector store into search router
    setattr(search_router.get_vector_store, "store", vector_store)

# Setup dependencies
setup_dependencies()

@app.get("/")
async def root():
    return {
        "message": "Welcome to CodeRAG API",
        "docs": "/docs",
        "health": "/api/health",
    }

if __name__ == "__main__":
    import uvicorn
    
    logger.info("Starting CodeRAG API...")
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.reload,
        log_level="info" if settings.debug else "warning",
    )