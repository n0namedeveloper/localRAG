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

from datetime import datetime

from app.config import settings, INDEX_DIR
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
        repo_url = repo_url.split("#")[0]
        repo_name = self.repo_manager.get_repo_name(repo_url)
        # Don't hardcode 'main' — let repo_manager detect the actual branch

        logger.info(f"🚀 Starting ingestion for {repo_url} (branch={branch or 'default'})")

        # ── Step 0: Clone / update ──
        status = RepoStatus.INDEXING
        self._update_state(repo_name, "cloning")
        
        # Create directory immediately so frontend API /list sees it as 'indexing'
        repo_index_dir = INDEX_DIR / repo_name
        repo_index_dir.mkdir(parents=True, exist_ok=True)

        try:
            repo, repo_path, status = self.repo_manager.get_repo(
                repo_url, branch, github_token=settings.github_token
            )
            if status == RepoStatus.ERROR:
                self._update_state(repo_name, "error", {"error": "Failed to clone repository"})
                return {
                    "repo_name": repo_name,
                    "status": "error",
                    "error": "Failed to clone repository",
                }

            # Detect the actual branch that was checked out
            try:
                actual_branch = repo.active_branch.name
            except Exception:
                actual_branch = branch or "main"
            branch = actual_branch

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

            # ── Incremental Indexing Setup ──
            repo_index_dir = INDEX_DIR / repo_name
            repo_index_dir.mkdir(parents=True, exist_ok=True)
            hashes_file = repo_index_dir / "hashes.json"
            symbols_file = repo_index_dir / "symbols.json"

            old_hashes = {}
            if hashes_file.exists():
                try:
                    old_hashes = json.loads(hashes_file.read_text())
                except Exception:
                    pass

            cached_symbols_dict = {}
            if symbols_file.exists():
                try:
                    cached_symbols_dict = json.loads(symbols_file.read_text())
                except Exception:
                    pass

            if force_reindex:
                old_hashes = {}
                cached_symbols_dict = {}
                self.vector_store.delete_repo(repo_name)

            new_hashes = {}
            changed_files = []
            unchanged_files = []

            for file_path in source_files:
                rel_path = str(file_path.relative_to(repo_path))
                try:
                    source_bytes = file_path.read_bytes()
                    file_hash = hashlib.sha256(source_bytes).hexdigest()
                    new_hashes[rel_path] = file_hash

                    if rel_path not in old_hashes or old_hashes[rel_path] != file_hash:
                        changed_files.append((file_path, rel_path, source_bytes))
                    else:
                        unchanged_files.append(rel_path)
                except Exception as e:
                    logger.warning(f"Could not read {file_path}: {e}")

            deleted_files = [rp for rp in old_hashes if rp not in new_hashes]
            logger.info(f"Scan: {len(changed_files)} changed/new, {len(unchanged_files)} unchanged, {len(deleted_files)} deleted")

            # ── Step 2: Delete old vectors ──
            if not force_reindex:
                for rel_path in deleted_files:
                    self.vector_store.delete_file_chunks(repo_name, rel_path)
                    cached_symbols_dict.pop(rel_path, None)
                for _, rel_path, _ in changed_files:
                    self.vector_store.delete_file_chunks(repo_name, rel_path)

            # ── Step 3: Parse changed files ──
            self._update_state(repo_name, "parsing")
            parsed_changed_symbols: list[ParsedSymbol] = []
            for file_path, rel_path, source_bytes in changed_files:
                try:
                    symbols = self.parser.parse_file(Path(rel_path), source_bytes, repo_name, repo_url, branch)
                    cached_symbols_dict[rel_path] = [s.model_dump() for s in symbols]
                    parsed_changed_symbols.extend(symbols)
                except Exception as e:
                    logger.warning(f"Failed to parse {file_path}: {e}")

            # Combine all symbols for graph
            all_symbols: list[ParsedSymbol] = []
            for rel_path, sym_dicts in cached_symbols_dict.items():
                for s in sym_dicts:
                    all_symbols.append(ParsedSymbol(**s))

            logger.info(f"Parsed {len(parsed_changed_symbols)} new symbols. Total symbols: {len(all_symbols)}")

            # ── Step 4: Chunk & Embed ONLY changed files ──
            self._update_state(repo_name, "chunking")
            chunks = self.chunker.chunk_all(parsed_changed_symbols)
            logger.info(f"Generated {len(chunks)} chunks for {len(changed_files)} changed files")

            self._update_state(repo_name, "indexing")
            if chunks:
                self.vector_store.index_chunks(chunks)

            # Save caches
            hashes_file.write_text(json.dumps(new_hashes, indent=2))
            symbols_file.write_text(json.dumps(cached_symbols_dict, indent=2, default=str))

            # ── Step 5: Build dependency graph ──
            self._update_state(repo_name, "building_graph")
            graph = self.dep_graph.build(all_symbols)
            logger.info(
                f"Graph built: {graph.number_of_nodes()} nodes, "
                f"{graph.number_of_edges()} edges"
            )

            # ── Step 7: Save state and meta.json for Dashboard ──
            duration = time.time() - start_time
            total_chunks = self.vector_store.count_chunks(repo_name)
            meta = {
                "repo_name": repo_name,
                "repo_url": repo_url,
                "branch": branch,
                "files_parsed": len(source_files),
                "symbols_count": len(all_symbols),
                "chunks_count": total_chunks,
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
                "duration_sec": round(duration, 2),
                "last_indexed": datetime.utcnow().isoformat(),
            }
            self._update_state(repo_name, "ready", meta)

            # Write meta.json so /api/repo/list can discover this repo
            repo_index_dir = INDEX_DIR / repo_name
            repo_index_dir.mkdir(parents=True, exist_ok=True)
            (repo_index_dir / "meta.json").write_text(
                json.dumps(meta, indent=2, default=str)
            )

            # Get git hotspots
            hotspots = self.repo_manager.get_git_hotspots(repo_path)

            # Save graph.json for /api/graph/:repo_name
            nodes_data = []
            for n in graph.nodes:
                data = graph.nodes[n].copy()
                file_path_str = data.get("file_path", "").replace("\\", "/")
                data["commit_count"] = hotspots.get(file_path_str, 0)
                nodes_data.append({"id": str(n), "data": data})

            graph_data = {
                "repo_name": repo_name,
                "nodes": nodes_data,
                "edges": [
                    {"id": f"{u}->{v}", "source": str(u), "target": str(v),
                     "label": str(graph.edges[u, v].get("dep_type", "depends")),
                     "weight": float(graph.edges[u, v].get("weight", 1.0))}
                    for u, v in graph.edges
                ],
            }
            (repo_index_dir / "graph.json").write_text(
                json.dumps(graph_data, indent=2, default=str)
            )

            logger.info(f"✅ Ingestion complete for {repo_url} in {duration:.1f}s")

            return {
                "repo_name": repo_name,
                "status": "ready",
                "files_parsed": len(source_files),
                "symbols_count": len(all_symbols),
                "chunks_count": total_chunks,
                "graph_nodes": graph.number_of_nodes(),
                "graph_edges": graph.number_of_edges(),
                "duration_sec": round(duration, 2),
            }
        except Exception as e:
            logger.exception(f"Fatal error during ingestion of {repo_url}")
            self._update_state(repo_name, "error", {"error": str(e)})
            return {
                "repo_name": repo_name,
                "status": "error",
                "error": str(e)
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