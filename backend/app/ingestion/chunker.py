"""
AST-aware chunking strategy.

Each function/class becomes one chunk (semantic unit).
Generates:
  - A "signature" chunk (name + signature + docstring) — for matching query intent
  - A "full code" chunk (entire source) — for retrieving implementation details
"""

import hashlib
import logging

from app.models.schemas import ParsedSymbol, CodeChunk, ChunkMetadata, SymbolType

logger = logging.getLogger(__name__)


class CodeChunker:
    """
    Converts ParsedSymbols into embeddable CodeChunks.

    Strategy:
      - Signature chunk: light, focused on meaning (name, signature, docstring, decorators)
      - Body chunk: full source code (for detailed implementation questions)
      - Import chunks: standalone imports (for dependency tracing)
    """

    SIGNATURE_CHUNK_PREFIX = "[SIGNATURE]"
    CODE_CHUNK_PREFIX = "[CODE]"
    IMPORT_CHUNK_PREFIX = "[IMPORT]"

    def chunk_symbol(self, symbol: ParsedSymbol) -> list[CodeChunk]:
        """
        Create 1-2 chunks from a single symbol.

        Returns:
            - 1 chunk for imports (compact)
            - 2 chunks for functions/classes (signature + full body)
        """
        if symbol.symbol_type == SymbolType.IMPORT:
            return [self._make_import_chunk(symbol)]

        chunks: list[CodeChunk] = []

        # Chunk 1: Signature (high-level understanding)
        signature_chunk = self._make_signature_chunk(symbol)
        if signature_chunk:
            chunks.append(signature_chunk)

        # Chunk 2: Full source code (detailed implementation)
        body_chunk = self._make_body_chunk(symbol)
        if body_chunk:
            chunks.append(body_chunk)

        return chunks

    def _make_signature_chunk(self, symbol: ParsedSymbol) -> CodeChunk | None:
        """Create a chunk focused on the symbol's signature and documentation."""
        parts: list[str] = []

        # Decorators (Python)
        if symbol.decorators:
            parts.append("Decorators: " + ", ".join(symbol.decorators))

        # Visibility
        if symbol.visibility:
            parts.append(f"Visibility: {symbol.visibility}")

        # Parent class context
        if symbol.parent_class:
            parts.append(f"Defined in class: {symbol.parent_class}")

        # Signature
        if symbol.signature:
            parts.append(f"Signature: {symbol.signature}")
        else:
            parts.append(f"{symbol.symbol_type.value}: {symbol.name}")

        # Docstring
        if symbol.docstring:
            parts.append(f"Documentation: {symbol.docstring}")

        # Dependencies summary
        if symbol.dependencies:
            parts.append(f"Calls: {', '.join(symbol.dependencies[:10])}")

        text = "\n".join(parts)
        if len(text.strip()) < 10:
            return None

        text = f"{self.SIGNATURE_CHUNK_PREFIX} {symbol.language} {symbol.symbol_type.value} {symbol.name}\n{text}"

        chunk_id = hashlib.sha256(
            f"{symbol.id}:signature".encode()
        ).hexdigest()[:16]

        metadata = self._build_metadata(symbol, "signature")

        return CodeChunk(id=chunk_id, symbol_id=symbol.id, text=text, metadata=metadata)

    def _make_body_chunk(self, symbol: ParsedSymbol) -> CodeChunk | None:
        """Create a chunk containing the full source code of the symbol."""
        if not symbol.source_code or len(symbol.source_code.strip()) < 10:
            return None

        # Truncate very long functions to avoid embedding issues
        source = symbol.source_code
        max_len = 6000
        if len(source) > max_len:
            source = source[:max_len] + "\n# ... (truncated)"

        text = f"{self.CODE_CHUNK_PREFIX} {symbol.language} {symbol.symbol_type.value} {symbol.name}\nFile: {symbol.file_path}\nLines: {symbol.start_line}-{symbol.end_line}\n\n{source}"

        chunk_id = hashlib.sha256(
            f"{symbol.id}:body".encode()
        ).hexdigest()[:16]

        metadata = self._build_metadata(symbol, "code")

        return CodeChunk(id=chunk_id, symbol_id=symbol.id, text=text, metadata=metadata)

    def _make_import_chunk(self, symbol: ParsedSymbol) -> CodeChunk:
        """Create a compact chunk for import statements."""
        text = f"{self.IMPORT_CHUNK_PREFIX} {symbol.language} import\nFile: {symbol.file_path}\nImport: {symbol.source_code}"

        chunk_id = hashlib.sha256(
            f"{symbol.id}:import".encode()
        ).hexdigest()[:16]

        metadata = self._build_metadata(symbol, "import")

        return CodeChunk(id=chunk_id, symbol_id=symbol.id, text=text, metadata=metadata)

    def _build_metadata(
        self, symbol: ParsedSymbol, chunk_type: str
    ) -> ChunkMetadata:
        """Build metadata payload for Qdrant."""
        return ChunkMetadata(
            symbol_id=symbol.id,
            symbol_name=symbol.name,
            symbol_type=symbol.symbol_type,
            file_path=symbol.file_path,
            start_line=symbol.start_line,
            end_line=symbol.end_line,
            language=symbol.language,
            signature=symbol.signature,
            parent_class=symbol.parent_class,
            repo_name=symbol.repo_name,
            repo_url=symbol.repo_url,
            branch=symbol.branch,
            dependencies=symbol.dependencies,
            chunk_type=chunk_type,
        )

    def chunk_all(self, symbols: list[ParsedSymbol]) -> list[CodeChunk]:
        """Chunk a list of symbols."""
        all_chunks: list[CodeChunk] = []
        for sym in symbols:
            chunks = self.chunk_symbol(sym)
            all_chunks.extend(chunks)
        logger.info(
            f"Chunked {len(symbols)} symbols into {len(all_chunks)} chunks"
        )
        return all_chunks