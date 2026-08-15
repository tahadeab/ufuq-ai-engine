"""
Ufuq AI Engine — إعدادات موحدة.

المبدأ المعماري: كل ما يتعلق بالتقنيات (أي LLM، أي Vector DB، أي نماذج)
يُضبط من هنا ومن ملف .env فقط. منطق العمل لا يحتوي على أسماء تقنيات.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ────────────────────────────────
    # وضع التشغيل العام
    # ────────────────────────────────
    ai_mode: str = Field(default="local", description="local | cloud")
    ci_mode: bool = False  # CI/test mode — no real LLM calls
    use_in_memory_store: bool = False  # True → InMemory store (no Qdrant server)

    def _qdrant_available(self) -> bool:
        """تحقق سريع من توفر خادم Qdrant."""
        try:
            import urllib.request
            with urllib.request.urlopen(
                f"http://{self.qdrant_host}:{self.qdrant_port}/healthz", timeout=2
            ):
                return True
        except Exception:
            return False

    def should_use_in_memory(self) -> bool:
        """True when ci_mode is on or Qdrant server unreachable."""
        if self.ci_mode:
            return True
        return not self._qdrant_available()

    def is_local_mode(self) -> bool:
        """هل يعمل المحرك محلياً (Ollama + BGE-M3)؟"""
        return self.ai_mode.lower() == "local" and self.llm_provider.lower() in (
            "ollama", "local")

    # ────────────────────────────────
    # LLM
    # ────────────────────────────────
    llm_provider: str = Field(default="ollama", description="ollama | openai | gemini")
    llm_model: str = Field(default="qwen3:8b")
    ollama_base_url: str = "http://localhost:11434"
    openai_api_key: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4.1-mini"
    gemini_api_key: Optional[str] = None
    gemini_model: str = "gemini-2.5-flash"
    llm_max_tokens: int = 4096
    temperature_extraction: float = Field(
        default=0.1, description="منخفضة لاستخراج JSON المنظم"
    )
    temperature_generation: float = 0.4

    # ────────────────────────────────
    # Embeddings
    # ────────────────────────────────
    embedding_model: str = "BAAI/bge-m3"
    embedding_dim: int = 1024
    embedding_device: str = "auto"  # auto | cpu | cuda
    embedding_batch_size: int = Field(default=8, ge=1, le=128)

    # ────────────────────────────────
    # Vector Store (Qdrant)
    # ────────────────────────────────
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_collection: str = "ufuq_chunks"

    # ────────────────────────────────
    # Relational DB (PostgreSQL — AI metadata)
    # ────────────────────────────────
    database_url: str = "postgresql+asyncpg://ufuq:ufuq@localhost:5432/ufuq_ai"

    # ────────────────────────────────
    # Ingestion
    # ────────────────────────────────
    storage_dir: Path = Field(default=BASE_DIR / "storage" / "sources")
    chunk_target_words: int = 400
    chunk_overlap_words: int = 60
    max_chunk_words: int = 900

    # ────────────────────────────────
    # RAG
    # ────────────────────────────────
    rag_top_k: int = 10
    rag_rerank_top_k: int = 5
    rag_reranker_enabled: bool = False  # يُفعَّل إذا توفر VRAM كافٍ
    reranker_model: str = "BAAI/bge-reranker-v2-m3"

    # ────────────────────────────────
    # Knowledge Graph
    # ────────────────────────────────
    graph_backend: str = Field(
        default="postgres", description="postgres | neo4j"
    )
    neo4j_uri: Optional[str] = None
    neo4j_user: Optional[str] = None
    neo4j_password: Optional[str] = None
    min_relationship_confidence: float = 0.5

    # ────────────────────────────────
    # Agent
    # ────────────────────────────────
    agent_max_retries: int = 3
    agent_max_steps: int = 60

    # ────────────────────────────────
    # MCP (مستقبلي)
    # ────────────────────────────────
    mcp_enabled: bool = False
    mcp_transport: str = "stdio"  # stdio | sse

    # ────────────────────────────────
    # عام
    # ────────────────────────────────
    app_name: str = "Ufuq AI Engine"
    log_level: str = "INFO"


_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Singleton للإعدادات — يُقرأ .env مرة واحدة."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# shortcut للوصول السريع داخل الوحدات
settings = get_settings()
