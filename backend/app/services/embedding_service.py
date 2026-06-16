"""
Embedding service — wraps sentence-transformers for generating text embeddings.
Model: sentence-transformers/all-MiniLM-L6-v2 (default)
       BAAI/bge-base-en-v1.5 (optional, better quality)
"""
import os
from typing import List

from backend.app.config import config
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

_model = None  # lazy-loaded singleton


def _apply_hf_token() -> None:
    """Propagate Hugging Face token for authenticated Hub downloads."""
    token = config.HF_TOKEN
    if not token:
        return
    os.environ.setdefault("HF_TOKEN", token)
    os.environ.setdefault("HUGGING_FACE_HUB_TOKEN", token)


def warmup_embedding_model() -> None:
    """Load the embedding model before parallel ingest work starts."""
    _get_model()


def _get_model():
    """Lazy-load the embedding model (loads once on first call)."""
    global _model
    if _model is None:
        _apply_hf_token()
        from sentence_transformers import SentenceTransformer

        logger.info(f"Loading embedding model: {config.EMBEDDING_MODEL}")
        model_kwargs = {}
        if config.HF_TOKEN:
            model_kwargs["token"] = config.HF_TOKEN
        _model = SentenceTransformer(config.EMBEDDING_MODEL, **model_kwargs)
        logger.info("Embedding model loaded successfully")
    return _model


def embed_texts(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of text strings.

    Args:
        texts: List of strings to embed

    Returns:
        List of embedding vectors (list of floats)
    """
    if not texts:
        return []

    model = _get_model()
    embeddings = model.encode(
        texts,
        batch_size=config.INGEST_EMBED_BATCH_SIZE,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return embeddings.tolist()


def embed_query(query: str) -> List[float]:
    """
    Generate a single query embedding.

    Args:
        query: The query string to embed

    Returns:
        A single embedding vector
    """
    result = embed_texts([query])
    return result[0] if result else []
