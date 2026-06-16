"""
Content accuracy — semantic similarity between generated resume and retrieved context.
Uses BAAI/bge-base-en-v1.5 (separate from ingestion embedding model).
"""
import os
from typing import Any, Dict, List

from backend.app.config import config
from backend.evaluation._utils import clamp_percent

_BGE_MODEL = None
EVAL_EMBEDDING_MODEL = os.getenv(
    "EVAL_EMBEDDING_MODEL", "BAAI/bge-base-en-v1.5"
)


def _get_bge_model():
    global _BGE_MODEL
    if _BGE_MODEL is None:
        from sentence_transformers import SentenceTransformer

        token = config.HF_TOKEN or None
        _BGE_MODEL = SentenceTransformer(EVAL_EMBEDDING_MODEL, token=token)
    return _BGE_MODEL


def embed_texts_bge(texts: List[str]) -> List[List[float]]:
    if not texts:
        return []
    model = _get_bge_model()
    vectors = model.encode(
        texts,
        batch_size=16,
        show_progress_bar=False,
        normalize_embeddings=True,
        convert_to_numpy=True,
    )
    return vectors.tolist()


def cosine_similarity_percent(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    return clamp_percent(dot * 100.0)


def build_context_corpus(chunks: List[Dict[str, Any]]) -> str:
    parts = []
    for chunk in chunks:
        text = chunk.get("text", "")
        if text:
            parts.append(text)
    return "\n".join(parts)


def compute_content_accuracy(
    resume_text: str,
    context_chunks: List[Dict[str, Any]],
) -> float:
    """Content Accuracy = embedding similarity (resume vs retrieved context) as %."""
    context = build_context_corpus(context_chunks)
    if not resume_text.strip() or not context.strip():
        return 0.0

    resume_emb, context_emb = embed_texts_bge([resume_text, context])
    return cosine_similarity_percent(resume_emb, context_emb)
