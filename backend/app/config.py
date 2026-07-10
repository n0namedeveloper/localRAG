"""Application configuration via pydantic-settings, loaded from .env."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # DeepSeek
    deepseek_api_key: str = ""
    deepseek_base_url: str = "https://api.deepseek.com/v1"
    deepseek_model: str = "deepseek-chat"
    deepseek_chat_completions_path: str = "/chat/completions"

    # Embeddings
    embedding_provider: str = "bge-m3"  # "bge-m3" or "openai"
    openai_api_key: str = ""

    # Qdrant
    qdrant_host: str = "qdrant"
    qdrant_port: int = 6333
    qdrant_collection_name: str = "code_chunks"

    # GitHub
    github_token: str = ""

    # Application
    data_dir: str = "./data"
    grammars_dir: str = "./grammars"
    allowed_origins: list[str] = ["*"]
    max_chunks_per_query: int = 15
    max_graph_hops: int = 1
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    debug: bool = False

    # Local model name (for sentence-transformers)
    local_embedding_model: str = "BAAI/bge-m3"
    embedding_dimension: int = 1024  # BGE-M3 dim

    # Language support
    supported_languages: list[str] = [
        "python",
        "javascript",
        "typescript",
        "go",
        "rust",
        "java",
        "cpp",
    ]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    @property
    def repos_dir(self) -> Path:
        return Path(self.data_dir) / "repos"

    @property
    def grammars_path(self) -> Path:
        return Path(self.grammars_dir)


settings = Settings()