"""
Configuration module — loads all settings from .env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# ── Locate project root and load .env ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")


def _apply_hf_token_from_env() -> None:
    """Set HF Hub env vars early so all libraries see the token."""
    token = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN", "")
    if token:
        os.environ.setdefault("HF_TOKEN", token)
        os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)


_apply_hf_token_from_env()


class Config:
    # ── NVIDIA NIM ────────────────────────────────────────────────────────────
    NVIDIA_API_KEY: str = os.getenv("NVIDIA_API_KEY", "")
    NVIDIA_BASE_URL: str = os.getenv(
        "NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1"
    )
    NVIDIA_MODEL: str = os.getenv(
        "NVIDIA_MODEL", "meta/llama-3.1-70b-instruct"
    )

    # ── Paths ─────────────────────────────────────────────────────────────────
    DATA_PATH: Path = PROJECT_ROOT / os.getenv("DATA_PATH", "data/data")
    CHROMA_PERSIST_PATH: Path = PROJECT_ROOT / os.getenv(
        "CHROMA_PERSIST_PATH", "backend/chroma_db"
    )
    GENERATED_RESUMES_PATH: Path = PROJECT_ROOT / os.getenv(
        "GENERATED_RESUMES_PATH", "backend/generated_resumes"
    )

    # ── Hugging Face (embedding model download) ───────────────────────────────
    HF_TOKEN: str = os.getenv("HF_TOKEN") or os.getenv("HUGGING_FACE_HUB_TOKEN", "")

    # ── Embedding ─────────────────────────────────────────────────────────────
    EMBEDDING_MODEL: str = os.getenv(
        "EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2"
    )

    # ── Ingestion performance ─────────────────────────────────────────────────
    INGEST_PDF_WORKERS: int = int(os.getenv("INGEST_PDF_WORKERS", "12"))
    INGEST_EMBED_BATCH_SIZE: int = int(os.getenv("INGEST_EMBED_BATCH_SIZE", "256"))
    INGEST_UPSERT_BATCH_SIZE: int = int(os.getenv("INGEST_UPSERT_BATCH_SIZE", "512"))
    INGEST_FAST_PDF: bool = os.getenv("INGEST_FAST_PDF", "true").lower() in (
        "1",
        "true",
        "yes",
    )
    INGEST_RESET_DB: bool = os.getenv("INGEST_RESET_DB", "false").lower() in (
        "1",
        "true",
        "yes",
    )

    # ── LLM generation params ─────────────────────────────────────────────────
    LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    LLM_TOP_P: float = float(os.getenv("LLM_TOP_P", "0.85"))
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "3000"))

    # ── Retrieval params ──────────────────────────────────────────────────────
    RETRIEVAL_TOP_K: int = int(os.getenv("RETRIEVAL_TOP_K", "12"))
    RETRIEVAL_FETCH_K: int = int(os.getenv("RETRIEVAL_FETCH_K", "30"))
    RERANKER_TOP_N: int = int(os.getenv("RERANKER_TOP_N", "7"))

    # ── ChromaDB collection name ──────────────────────────────────────────────
    CHROMA_COLLECTION: str = "resume_chunks"

    # ── Server ────────────────────────────────────────────────────────────────
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
    FRONTEND_ORIGIN: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    # ── Evaluation ────────────────────────────────────────────────────────────
    EVALUATION_REPORTS_PATH: Path = PROJECT_ROOT / "backend" / "evaluation" / "reports"
    EVAL_EMBEDDING_MODEL: str = os.getenv(
        "EVAL_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"
    )

    @classmethod
    def ensure_dirs(cls) -> None:
        """Create required output directories if they don't exist."""
        cls.CHROMA_PERSIST_PATH.mkdir(parents=True, exist_ok=True)
        cls.GENERATED_RESUMES_PATH.mkdir(parents=True, exist_ok=True)
        cls.EVALUATION_REPORTS_PATH.mkdir(parents=True, exist_ok=True)


config = Config()
config.ensure_dirs()
