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
embedding_provider = EmbeddingProvider()
vector_store = VectorStore(embedding_provider=embedding_provider)
dep_graph = DependencyGraph()
llm_client = DeepSeekClient()

# Initialize ingestion pipeline
pipeline = IngestionPipeline(
    vector_store=vector_store,
    dep_graph=dep_graph,
)

# Set components in globals for dependency injection
# (This is a simplified approach; in production, use DI containers)
from app.api.health import get_vector_store as health_get_vs, get_llm_client as health_get_llm
setattr(health_get_vs, "store", vector_store)
setattr(health_get_llm, "client", llm_client)

# Import the actual dependency functions (not the router attributes)
from app.api.chat import get_rag_engine as chat_get_rag_engine
from app.api.repo import get_pipeline as repo_get_pipeline, _pipeline_instance as repo_pipeline_instance
from app.api.search import get_vector_store as search_get_vs

# Initialize engine attribute to None on the actual function objects
setattr(chat_get_rag_engine, "engine", None)
# Set pipeline on the module-level variable used by repo.py's get_pipeline function
import app.api.repo as repo_module
repo_module._pipeline_instance = pipeline
setattr(search_get_vs, "store", vector_store)

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
    # Inject engine into the actual get_rag_engine function used by FastAPI Depends()
    setattr(chat_get_rag_engine, "engine", RAGEngine(
        vector_store=vector_store,
        llm_client=llm_client,
        dep_graph=dep_graph,
    ))

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