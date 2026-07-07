"""
RAG Engine — the core orchestration component.

Pipeline:
  1. Receive query + repo
  2. Vector search in Qdrant (dense retrieval)
  3. Graph traversal for +1 hop context
  4. Build contextual prompt from chunks
  5. Call DeepSeek via LLM client
  6. Parse answer to extract source references
"""

import logging
import re
from typing import AsyncGenerator, Optional

from app.config import settings
from app.models.schemas import (
    ChatRequest,
    ChatResponse,
    SourceReference,
    ChunkMetadata,
    SymbolType,
)
from app.core.vector_store import VectorStore
from app.core.llm_client import DeepSeekClient, SYSTEM_PROMPT
from app.ingestion.graph_builder import DependencyGraph

logger = logging.getLogger(__name__)


class RAGEngine:
    """
    Orchestrates end-to-end RAG: search → enrich → prompt → generate.

    Usage:
        engine = RAGEngine(vector_store, llm_client, dep_graph)
        response = engine.answer(chat_request)
    """

    def __init__(
        self,
        vector_store: VectorStore,
        llm_client: DeepSeekClient,
        dep_graph: DependencyGraph,
    ):
        self.vector_store = vector_store
        self.llm = llm_client
        self.dep_graph = dep_graph

    def answer(self, request: ChatRequest) -> ChatResponse:
        """
        Full RAG pipeline (synchronous).

        Args:
            request: ChatRequest with repo_url and question.

        Returns:
            ChatResponse with answer text and source references.
        """
        # 1. Vector retrieval
        chunks = self._retrieve_chunks(
            query=request.question,
            repo_url=request.repo_url,
            top_k=request.max_chunks,
        )

        # 2. Graph enrichment (expand with +1 hop neighbors)
        enriched = self._enrich_with_graph(chunks, hops=settings.max_graph_hops)

        # 3. Build augmented prompt
        prompt = self._build_prompt(request.question, enriched)

        # 4. Generate answer
        answer_text = self.llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )

        # 5. Parse sources from the answer text
        sources = self._extract_sources(answer_text, chunks)

        # 6. Build GitHub permalinks
        repo_name = self._extract_repo_name(request.repo_url)
        for source in sources:
            source.github_url = self._build_github_url(
                request.repo_url, source.file_path, source.start_line
            )

        return ChatResponse(
            answer=answer_text,
            sources=sources,
            repo_name=repo_name,
            question=request.question,
        )

    async def answer_stream(
        self, request: ChatRequest
    ) -> AsyncGenerator[str, None]:
        """
        Streaming RAG pipeline.

        Yields SSE chunks: token text and final JSON with sources.
        """
        # 1-3. Same retrieval + enrichment
        chunks = self._retrieve_chunks(
            query=request.question,
            repo_url=request.repo_url,
            top_k=request.max_chunks,
        )
        enriched = self._enrich_with_graph(chunks, hops=settings.max_graph_hops)
        prompt = self._build_prompt(request.question, enriched)

        # 4. Stream tokens
        full_answer = ""
        async for token in self.llm.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
        ):
            full_answer += token
            yield token

        # 5. Parse sources
        sources = self._extract_sources(full_answer, chunks)
        repo_name = self._extract_repo_name(request.repo_url)
        for source in sources:
            source.github_url = self._build_github_url(
                request.repo_url, source.file_path, source.start_line
            )

        # 6. Yield final JSON with sources (sentinel for client)
        import json
        final_payload = json.dumps(
            {
                "type": "sources",
                "sources": [s.model_dump() for s in sources],
                "repo_name": repo_name,
            }
        )
        yield f"\n\n<!-- SOURCES:{final_payload} -->"

    def _retrieve_chunks(
        self, query: str, repo_url: str, top_k: int
    ) -> list[tuple[ChunkMetadata, float]]:
        """Vector search + symbol name search for robustness."""
        repo_name = self._extract_repo_name(repo_url)

        # Primary: semantic vector search
        results = self.vector_store.search(
            query=query,
            repo_name=repo_name,
            top_k=top_k,
            score_threshold=0.3,
        )
        return results

    def _enrich_with_graph(
        self,
        chunks: list[tuple[ChunkMetadata, float]],
        hops: int = 1,
    ) -> list[tuple[ChunkMetadata, float]]:
        """Expand results with graph neighbors (+1 hop)."""
        seen_ids = set()
        enriched: list[tuple[ChunkMetadata, float]] = []

        for meta, score in chunks:
            seen_ids.add(meta.symbol_id)
            enriched.append((meta, score))

            # Get neighbors from graph
            neighbor_ids = self.dep_graph.get_neighbors(meta.symbol_id, hops=hops)
            for nid in neighbor_ids:
                if nid not in seen_ids and nid in self.dep_graph.graph:
                    seen_ids.add(nid)
                    # Build a pseudo-metadata for the neighbor
                    node_data = self.dep_graph.graph.nodes[nid]
                    neighbor_meta = ChunkMetadata(
                        symbol_id=nid,
                        symbol_name=node_data.get("name", "unknown"),
                        symbol_type=SymbolType(
                            node_data.get("symbol_type", "function")
                        ),
                        file_path=node_data.get("file_path", ""),
                        start_line=0,
                        end_line=0,
                        language="",
                        repo_name=meta.repo_name,
                        dependencies=[],
                    )
                    # Give lower score than the matched chunk
                    enriched.append((neighbor_meta, score * 0.6))

        return enriched

    def _build_prompt(
        self,
        question: str,
        chunks: list[tuple[ChunkMetadata, float]],
    ) -> str:
        """Build an augmented prompt with code context."""
        sections = []
        sections.append("## Relevant code from the repository\n")

        for i, (meta, score) in enumerate(chunks):
            file_line = f"{meta.file_path}:{meta.start_line}-{meta.end_line}"
            header = f"[{i+1}] {meta.symbol_name} ({meta.symbol_type.value}) — {file_line}"
            if meta.parent_class:
                header += f" — class: {meta.parent_class}"

            # If we have the symbol signature from earlier context
            sig = f" {meta.signature}" if meta.signature else ""
            sections.append(f"### {header}\n{sig}")

        sections.append("\n## User Question\n")
        sections.append(question)

        return "\n\n".join(sections)

    def _extract_sources(
        self,
        answer: str,
        chunks: list[tuple[ChunkMetadata, float]],
    ) -> list[SourceReference]:
        """Parse source references from LLM answer and match to chunks."""
        sources: list[SourceReference] = []

        # Pattern: [src/file_path:line] or [src/file_path:start-end]
        pattern = r"\[src/([^:\]]+):(\d+)(?:-(\d+))?\]"
        matches = re.findall(pattern, answer)

        file_chunks: dict[str, tuple[ChunkMetadata, float]] = {}
        for meta, score in chunks:
            key = meta.file_path
            if key not in file_chunks or score > file_chunks[key][1]:
                file_chunks[key] = (meta, score)

        for file_path, start, end in matches:
            end_line = int(end) if end else int(start)
            start_line = int(start)

            meta = file_chunks.get(file_path)
            if meta:
                meta_obj, score = meta
                sources.append(
                    SourceReference(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        symbol_name=meta_obj.symbol_name,
                        symbol_type=meta_obj.symbol_type,
                        snippet=meta_obj.signature[:200],
                        relevance_score=score,
                    )
                )
            else:
                # No metadata found — still add a reference
                sources.append(
                    SourceReference(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        symbol_name="",
                        relevance_score=0.0,
                    )
                )

        return sources

    def _build_github_url(
        self, repo_url: str, file_path: str, line: int
    ) -> str:
        """Build a GitHub permalink to a specific line."""
        repo_url = repo_url.rstrip(".git").rstrip("/")
        return f"{repo_url}/blob/main/{file_path}#L{line}"

    def _extract_repo_name(self, repo_url: str) -> str:
        """Extract owner/repo from GitHub URL."""
        m = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+)", repo_url)
        if m:
            return m.group(1).replace(":", "/")
        return repo_url