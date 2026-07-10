"""
Ingestion Pipeline — orchestrates the full indexing workflow.

Flow:
  clone/pull repo
  → walk source files
  → parse each file (tree-sitter)
  → chunk symbols (AST-aware)
  → embed + index into Qdrant
  → build dependency graph
"""

import hashlib
import json
import logging
import time
from pathlib import Path

from app.config import settings
from app.models.schemas import ParsedSymbol, RepoStatus
from app.ingestion.parser import CodeParser
from app.ingestion.chunker import CodeChunker
from app.ingestion.graph_builder import DependencyGraph
from app.ingestion.repo_manager import RepoManager
from app.core.vector_store import VectorStore
from app.core.embedding import EmbeddingProvider

logger = logging.getLogger(__name__)


class IngestionPipeline:
    """
    End-to-end ingestion: Git → parser → chunker → embedder → Qdrant + graph.

    Usage:
        pipeline = IngestionPipeline(vector_store, dep_graph)
        result = pipeline.run("https://github.com/user/repo")
    """

    def __init__(
        self,
        vector_store: VectorStore,
        dep_graph: DependencyGraph,
    ):
        self.vector_store = vector_store
        self.dep_graph = dep_graph
        self.parser = CodeParser()
        self.chunker = CodeChunker()
        self.repo_manager = RepoManager()
        self.embedder = EmbeddingProvider()

        # Track indexing state per repo
        self._state_file = settings.repos_dir / ".index_state.json"
        self._state: dict[str, dict] = self._load_state()

    def run(
        self,
        repo_url: str,
        branch: str | None = None,
        force_reindex: bool = False,
    ) -> dict:
        """
        Execute full ingestion pipeline.

        Args:
            repo_url: GitHub repository URL.
            branch: Git branch to index.
            force_reindex: If True, re-clone and re-index from scratch.

        Returns:
            Dict with pipeline stats:
                repo_name, status, files_parsed, symbols_count,
                chunks_count, graph_nodes, graph_edges, duration_sec
        """
        start_time = time.time()
        repo_name = self.repo_manager.get_repo_name(repo_url)

        logger.info(f"🚀 Starting ingestion for {repo_url} (branch={branch})")

        # ── Step 0: Clone / update ──
        status = RepoStatus.INDEXING
        self._update_state(repo_name, "cloning")

        repo, repo_path, status = self.repo_manager.get_repo(
            repo_url, branch, github_token=settings.github_token
        )
        if status == RepoStatus.ERROR:
            self._update_state(repo_name, "error")
            return {
                "repo_name": repo_name,
                "status": "error",
                "error": "Failed to clone repository",
            }

        # ── Step 1: List source files ──
        self._update_state(repo_name, "scanning")
        source_files = self.repo_manager.list_source_files(repo_path)
        if not source_files:
            logger.warning(f"No supported source files found in {repo_path}")
            self._update_state(repo_name, "ready")
            return {
                "repo_name": repo_name,
                "status": "ready",
                "files_parsed": 0,
                "symbols_count": 0,
                "chunks_count": 0,
                "graph_nodes": 0,
                "graph_edges": 0,
                "duration_sec": time.time() - start_time,
            }

        # ── Step 2: Parse all files ──
        self._update_state(repo_name, "parsing")
        all_symbols: list[ParsedSymbol] = []
        for file_path in source_files:
            try:
                source = file_path.read_bytes()
                rel_path = file_path.relative_to(repo_path)
                symbols = self.parser.parse_file(
                    rel_path, source, repo_name, repo_url, branch
                )
                all_symbols.extend(symbols)
            except Exception as e:
                logger.warning(f"Failed to parse {file_path}: {e}")

        logger.info(f"Parsed {len(all_symbols)} symbols from {len(source_files)} files")

        # ── Step 3: Chunk symbols ──
        self._update_state(repo_name, "chunking")
        chunks = self.chunker.chunk_all(all_symbols)
        logger.info(f"Generated {len(chunks)} chunks")

        # ── Step 4: Delete old data for this repo (if re-indexing) ──
        if force_reindex:
            self.vector_store.delete_repo(repo_name)

        # ── Step 5: Embed and index into Qdrant ──
        self._update_state(repo_name, "indexing")
        indexed_result = self.vector_store.index_chunks(chunks)
        # indexed_result is an UpdateResult object; use the number of chunks provided as the count
        indexed_count = len(chunks)
        logger.info(f"Indexed {indexed_count} chunks into Qdrant")

        # ── Step 6: Build dependency graph ──
        self._update_state(repo_name, "building_graph")
        graph = self.dep_graph.build(all_symbols)
        logger.info(
            f"Graph built: {graph.number_of_nodes()} nodes, "
            f"{graph.number_of_edges()} edges"
        )

        # ── Step 7: Save state ──
        duration = time.time() - start_time
        self._update_state(repo_name, "ready", {
            "files_parsed": len(source_files),
            "symbols_count": len(all_symbols),
            "chunks_count": len(chunks),
            "graph_nodes": graph.number_of_nodes(),
            "graph_edges": graph.number_of_edges(),
            "duration_sec": round(duration, 2),
            "last_indexed": time.time(),
        })

        logger.info(f"✅ Ingestion complete for {repo_url} in {duration:.1f}s")

        return {
            "repo_name": repo_name,
            "status": "ready",
            "files_parsed": len(source_files),
            "symbols_count": len(all_symbols),
            "chunks_count": len(chunks),
            "graph_nodes": graph.number_of_nodes(),
            "graph_edges": graph.number_of_edges(),
            "duration_sec": round(duration, 2),
        }

    def get_repo_status(self, repo_url: str) -> RepoStatus:
        """Get the current status of a repository."""
        repo_name = self.repo_manager.get_repo_name(repo_url)
        state = self._state.get(repo_name, {})
        status_str = state.get("status", "not_found")
        try:
            return RepoStatus(status_str)
        except ValueError:
            return RepoStatus.NOT_FOUND

    def get_index_stats(self, repo_url: str) -> dict:
        """Get detailed indexing stats for a repository."""
        repo_name = self.repo_manager.get_repo_name(repo_url)
        return self._state.get(repo_name, {
            "status": "not_found",
            "files_parsed": 0,
            "symbols_count": 0,
            "chunks_count": 0,
            "graph_nodes": 0,
            "graph_edges": 0,
        })

    # ── State persistence ──

    def _load_state(self) -> dict:
        """Load indexing state from JSON."""
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_state(self):
        """Save indexing state to JSON."""
        self._state_file.parent.mkdir(parents=True, exist_ok=True)
        self._state_file.write_text(
            json.dumps(self._state, indent=2, default=str)
        )

    def _update_state(self, repo_name: str, status: str, extra: dict | None = None):
        """Update in-memory and persisted state for a repo."""
        if repo_name not in self._state:
            self._state[repo_name] = {}
        self._state[repo_name]["status"] = status
        if extra:
            self._state[repo_name].update(extra)
        self._save_state()