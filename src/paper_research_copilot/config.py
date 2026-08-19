"""Application settings loaded from environment variables and ``.env``."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Runtime configuration for the first RAG vertical slice."""

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    deepseek_api_key: SecretStr | None = None
    deepseek_api_url: str | None = None
    deepseek_model: str = "deepseek-v4-flash"

    relay_api_key: SecretStr | None = None
    relay_base_url: str | None = None
    gpt_model_name: str = "gpt-5.5"

    siliconflow_api_key: SecretStr | None = None
    siliconflow_base_url: str | None = None
    siliconflow_embedding_model: str = "BAAI/bge-m3"
    siliconflow_reranker_model: str = "BAAI/bge-reranker-v2-m3"
    embedding_dimension: int = 1024

    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    qdrant_path: Path = Path("data/qdrant")
    qdrant_collection: str = "agent_seed_v3_bge_m3_chunking_v1"

    chunking_version: str = "chunking_v1"
    chunk_size_chars: int = Field(default=3200, ge=200)
    chunk_overlap_chars: int = Field(default=400, ge=0)
    retrieval_top_k: int = Field(default=5, ge=1, le=20)
    answer_max_tokens: int = Field(default=2400, ge=256, le=8000)
    agent_planner_max_tokens: int = Field(default=1800, ge=256, le=4000)
    agent_top_k: int = Field(default=10, ge=1, le=20)
    agent_candidate_pool_per_task: int = Field(default=30, ge=1, le=100)
    agent_max_retries: int = Field(default=1, ge=0, le=1)
    agent_min_chunks_per_task: int = Field(default=2, ge=1, le=5)

    @model_validator(mode="after")
    def validate_chunking(self) -> "Settings":
        if self.chunk_overlap_chars >= self.chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be smaller than chunk_size_chars")
        if self.agent_candidate_pool_per_task < self.agent_top_k:
            raise ValueError("agent_candidate_pool_per_task must be at least agent_top_k")
        return self

    def require_embedding_credentials(self) -> tuple[str, str]:
        return self.require_siliconflow_credentials()

    def require_siliconflow_credentials(self) -> tuple[str, str]:
        if not self.siliconflow_base_url or not self.siliconflow_api_key:
            raise ValueError("SILICONFLOW_BASE_URL and SILICONFLOW_API_KEY are required")
        return self.siliconflow_base_url, self.siliconflow_api_key.get_secret_value()

    def require_llm_credentials(self) -> tuple[str, str]:
        if not self.deepseek_api_url or not self.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_URL and DEEPSEEK_API_KEY are required for answers")
        return self.deepseek_api_url, self.deepseek_api_key.get_secret_value()

    def require_relay_credentials(self) -> tuple[str, str]:
        if not self.relay_base_url or not self.relay_api_key:
            raise ValueError("RELAY_BASE_URL and RELAY_API_KEY are required for critical tasks")
        return self.relay_base_url, self.relay_api_key.get_secret_value()

    def resolved_qdrant_path(self) -> Path:
        if self.qdrant_path.is_absolute():
            return self.qdrant_path
        return PROJECT_ROOT / self.qdrant_path


@lru_cache
def get_settings() -> Settings:
    return Settings()
