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
from typing import AsyncGenerator

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
        dep_graph: DependencyGraph,
    ):
        self.vector_store = vector_store
        self.dep_graph = dep_graph

    def answer(self, request: ChatRequest) -> ChatResponse:
        """
        Full RAG pipeline (synchronous).

        Args:
            request: ChatRequest with repo_url and question.

        Returns:
            ChatResponse with answer text and source references.
        """
        chunks = self._retrieve_chunks(
            query=request.question,
            repo_url=request.repo_url,
            top_k=request.max_chunks,
        )
        enriched = self._enrich_with_graph(chunks, hops=settings.max_graph_hops)
        prompt = self._build_prompt(request.question, enriched)
        
        from app.core.llm_client import get_llm_client, SYSTEM_PROMPT
        llm = get_llm_client()
        
        answer_text = llm.chat(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
            temperature=0.2,
        )
        sources = self._extract_sources(answer_text, chunks)
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
    ) -> AsyncGenerator[str | list[SourceReference], None]:
        """
        Streaming RAG pipeline.

        Yields:
            - str tokens during generation
            - list[SourceReference] as the final item after streaming completes
        """
        chunks = self._retrieve_chunks(
            query=request.question,
            repo_url=request.repo_url,
            top_k=request.max_chunks,
        )
        enriched = self._enrich_with_graph(chunks, hops=settings.max_graph_hops)
        prompt = self._build_prompt(request.question, enriched)

        from app.core.llm_client import get_llm_client, SYSTEM_PROMPT
        llm = get_llm_client()

        full_answer = ""
        async for token in llm.chat_stream(
            messages=[{"role": "user", "content": prompt}],
            system_prompt=SYSTEM_PROMPT,
        ):
            full_answer += token
            yield token

        # Yield sources as the final item — no second vector search needed
        sources = self._extract_sources(full_answer, chunks)
        for source in sources:
            source.github_url = self._build_github_url(
                request.repo_url, source.file_path, source.start_line
            )
        yield sources

    def _retrieve_chunks(
        self, query: str, repo_url: str | None, top_k: int
    ) -> list[tuple[ChunkMetadata, float]]:
        """Vector search for relevant code chunks."""
        repo_name = self._extract_repo_name(repo_url) if repo_url else None
        
        # Check if the query asks about a specific file (e.g. from the UI "Explain" button)
        file_path_filter = None
        m = re.search(r'located in "([^"]+)"', query)
        if m:
            file_path_filter = m.group(1)

        return self.vector_store.search(
            query=query,
            repo_name=repo_name,
            top_k=top_k,
            score_threshold=0.3,
            file_path=file_path_filter,
        )

    def _enrich_with_graph(
        self,
        chunks: list[tuple[ChunkMetadata, float]],
        hops: int = 1,
    ) -> list[tuple[ChunkMetadata, float]]:
        """Expand results with graph neighbors (+1 hop)."""
        seen_ids: set[str] = set()
        enriched: list[tuple[ChunkMetadata, float]] = []

        for meta, score in chunks:
            seen_ids.add(meta.symbol_id)
            enriched.append((meta, score))

            for nid in self.dep_graph.get_neighbors(meta.symbol_id, hops=hops):
                if nid in seen_ids or nid not in self.dep_graph.graph:
                    continue
                seen_ids.add(nid)
                node_data = self.dep_graph.graph.nodes[nid]
                neighbor_meta = ChunkMetadata(
                    symbol_id=nid,
                    symbol_name=node_data.get("name", "unknown"),
                    symbol_type=SymbolType(node_data.get("symbol_type", "function")),
                    file_path=node_data.get("file_path", ""),
                    start_line=0,
                    end_line=0,
                    language="",
                    repo_name=meta.repo_name,
                    dependencies=[],
                )
                enriched.append((neighbor_meta, score * 0.6))

        return enriched

    def _build_prompt(
        self,
        question: str,
        chunks: list[tuple[ChunkMetadata, float]],
    ) -> str:
        """Build an augmented prompt with code context."""
        sections = ["## Relevant code from the repository\n"]

        for i, (meta, score) in enumerate(chunks):
            file_line = f"{meta.file_path}:{meta.start_line}-{meta.end_line}"
            header = f"[{i + 1}] {meta.symbol_name} ({meta.symbol_type.value}) — {file_line}"
            if meta.parent_class:
                header += f" — class: {meta.parent_class}"
            sig = f"\n```\n{meta.signature}\n```" if meta.signature else ""
            sections.append(f"### {header}{sig}")

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
        pattern = r"\[src/([^:\]]+):(\d+)(?:-(\d+))?\]"
        matches = re.findall(pattern, answer)

        file_chunks: dict[str, tuple[ChunkMetadata, float]] = {}
        for meta, score in chunks:
            if meta.file_path not in file_chunks or score > file_chunks[meta.file_path][1]:
                file_chunks[meta.file_path] = (meta, score)

        for file_path, start, end in matches:
            start_line = int(start)
            end_line = int(end) if end else start_line
            chunk = file_chunks.get(file_path)
            if chunk:
                meta_obj, score = chunk
                sources.append(
                    SourceReference(
                        file_path=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        symbol_name=meta_obj.symbol_name,
                        symbol_type=meta_obj.symbol_type,
                        snippet=meta_obj.signature[:200] if meta_obj.signature else "",
                        relevance_score=score,
                    )
                )
            else:
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

    def _build_github_url(self, repo_url: str | None, file_path: str, line: int) -> str:
        """Build a GitHub permalink to a specific line."""
        if not repo_url:
            return ""
        repo_url = repo_url.rstrip(".git").rstrip("/")
        return f"{repo_url}/blob/main/{file_path}#L{line}"

    def _extract_repo_name(self, repo_url: str | None) -> str | None:
        """Extract owner/repo from GitHub URL."""
        if not repo_url or repo_url.lower() == "all":
            return None
        m = re.search(r"github\.com[/:]([\w.-]+/[\w.-]+)", repo_url)
        if m:
            return m.group(1).replace(":", "/")
        return repo_url
