from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", env_ignore_empty=True)
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("")
    llm_provider: Literal["ollama"] = "ollama"
    llm_model: str = Field("qwen3:4b", min_length=1, max_length=150)
    extraction_model: str = Field("qwen3:4b", min_length=1, max_length=150)
    ollama_base_url: str = "http://localhost:11434"
    ollama_context_length: int = Field(16384, ge=2048, le=65536)
    # Unload after each serialized request to avoid retaining two large models.
    ollama_keep_alive: int = Field(0, ge=0, le=3600)
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384
    data_dir: Path = Path(".data")
    top_k: int = Field(8, ge=1, le=30)
    max_depth: int = Field(3, ge=1, le=5)
    path_limit: int = Field(40, ge=1, le=100)
    similarity_threshold: float = Field(0.15, ge=-1, le=1)
    chunk_size: int = Field(1200, ge=100, le=8000)
    chunk_overlap: int = Field(150, ge=0, le=2000)
    context_tokens: int = Field(6000, ge=256, le=32000)
    reranking: bool = True
    fusion: Literal["rrf", "weighted"] = "rrf"
    vector_weight: float = Field(0.5, ge=0, le=1)
    default_mode: Literal["auto", "vector", "graph", "hybrid"] = "auto"
    max_upload_mb: int = Field(20, ge=1, le=100)
    request_timeout: float = Field(180, ge=5, le=1800)
    max_output_tokens: int = Field(4096, ge=256, le=8192)
    requests_per_minute: int = 60
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    relationship_types: list[str] = [
        "FOUNDED",
        "WORKS_AT",
        "ACQUIRED",
        "PARTNERED_WITH",
        "DEVELOPED",
        "LOCATED_IN",
        "CREATED",
        "OWNS",
        "ASSOCIATED_WITH",
    ]

    @model_validator(mode="after")
    def overlap_valid(self):
        if self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")
        import ipaddress
        from urllib.parse import urlsplit

        url = urlsplit(self.ollama_base_url)
        host = url.hostname or ""
        try:
            local = ipaddress.ip_address(host).is_private or ipaddress.ip_address(host).is_loopback
        except ValueError:
            local = host in {"localhost", "host.docker.internal", "ollama"} or host.endswith(".local")
        if url.scheme != "http" or not local or url.username or url.password or url.query or url.fragment:
            raise ValueError("Ollama must use a local HTTP endpoint without credentials")
        for model in (self.llm_model, self.extraction_model):
            if "cloud" in model.casefold():
                raise ValueError("Select a locally installed Ollama model, not a cloud model")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
