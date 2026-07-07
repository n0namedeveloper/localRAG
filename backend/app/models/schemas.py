"""Core data models for LocalRAG — symbols, chunks, API request/response schemas."""

from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


# ─── Enums ───────────────────────────────────────────────────────

class SymbolType(str, Enum):
    FUNCTION = "function"
    METHOD = "method"
    CLASS = "class"
    MODULE = "module"
    VARIABLE = "variable"
    IMPORT = "import"
    INTERFACE = "interface"
    TYPE_ALIAS = "type_alias"
    ENUM = "enum"


class DependencyType(str, Enum):
    IMPORT = "import"
    INHERITANCE = "inheritance"
    CALL = "call"
    INSTANTIATE = "instantiate"
    DECORATOR = "decorator"


class RepoStatus(str, Enum):
    CLONING = "cloning"
    INDEXING = "indexing"
    READY = "ready"
    ERROR = "error"
    NOT_FOUND = "not_found"


# ─── Symbol & Dependency Models ──────────────────────────────────

class ParsedSymbol(BaseModel):
    """Represents a single code symbol extracted by tree-sitter."""

    id: str = Field(description="Unique id: {file_hash}:{name}:{type}:{line}")
    name: str
    symbol_type: SymbolType
    file_path: str  # relative path inside repo
    start_line: int
    end_line: int
    language: str  # python, javascript, etc.
    signature: str = ""
    docstring: str | None = None
    source_code: str = ""  # full body
    parent_class: str | None = None  # for methods / nested classes
    dependencies: list[str] = Field(default_factory=list)  # symbol names this depends on
    decorators: list[str] = Field(default_factory=list)
    visibility: str | None = None  # public/private/protected
    repo_name: str = ""
    repo_url: str = ""
    branch: str = "main"


class DependencyEdge(BaseModel):
    """Directed edge in the code dependency graph."""

    from_symbol_id: str
    to_symbol_id: str
    dep_type: DependencyType
    from_file: str
    to_file: str
    weight: float = 1.0  # for graph traversal ranking


# ─── Chunk Models (for embedding / vector store) ─────────────────

class ChunkMetadata(BaseModel):
    """Payload stored alongside each embedding vector in Qdrant."""

    symbol_id: str
    symbol_name: str
    symbol_type: SymbolType
    file_path: str
    start_line: int
    end_line: int
    language: str
    signature: str = ""
    parent_class: str | None = None
    repo_name: str
    repo_url: str = ""
    branch: str = "main"
    dependencies: list[str] = Field(default_factory=list)
    chunk_type: str = "code"  # "code" | "docstring" | "signature"


class CodeChunk(BaseModel):
    """A chunk ready for embedding and storing in Qdrant."""

    id: str
    symbol_id: str
    text: str  # the text that gets embedded
    metadata: ChunkMetadata
    embedding: list[float] | None = None  # populated after embedding


# ─── API Request / Response Schemas ──────────────────────────────

class RepoCloneRequest(BaseModel):
    repo_url: str = Field(
        description="GitHub repo URL, e.g. https://github.com/user/repo.git"
    )
    branch: str = "main"
    force_reindex: bool = False


class RepoStatusResponse(BaseModel):
    repo_url: str
    repo_name: str
    status: RepoStatus
    files_indexed: int = 0
    symbols_indexed: int = 0
    last_indexed: datetime | None = None
    error_message: str | None = None


class ChatRequest(BaseModel):
    repo_url: str
    question: str
    max_chunks: int = 15
    stream: bool = False


class SourceReference(BaseModel):
    """Concrete file:line reference in the answer."""

    file_path: str
    start_line: int
    end_line: int
    symbol_name: str
    symbol_type: SymbolType | None = None
    snippet: str = ""  # short code preview
    relevance_score: float = 0.0
    github_url: str = ""  # constructed GitHub permalink


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference]
    repo_name: str
    question: str


class SearchRequest(BaseModel):
    repo_url: str
    query: str
    top_k: int = 10


class SearchResult(BaseModel):
    chunks: list[CodeChunk]
    total: int


class HealthResponse(BaseModel):
    status: str = "ok"
    qdrant: str = "connected"
    version: str = "0.1.0"