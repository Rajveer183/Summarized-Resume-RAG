"""
Optional CrossEncoder reranker.
Uses: cross-encoder/ms-marco-MiniLM-L-6-v2

If the cross-encoder model is not available (import error or download fails),
falls back gracefully to distance-based ranking.
"""
from typing import Any, Dict, List

from backend.app.config import config
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

_reranker = None
_reranker_available = None  # None = not yet checked


def _get_reranker():
    """Lazy-load the CrossEncoder reranker model."""
    global _reranker, _reranker_available
    if _reranker_available is None:
        try:
            from sentence_transformers.cross_encoder import CrossEncoder
            _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
            _reranker_available = True
            logger.info("CrossEncoder reranker loaded successfully")
        except Exception as e:
            logger.warning(f"CrossEncoder unavailable, using fallback ranking: {e}")
            _reranker_available = False
    return _reranker if _reranker_available else None


def rerank(
    query: str,
    chunks: List[Dict[str, Any]],
    top_n: int = None,
) -> List[Dict[str, Any]]:
    """
    Rerank retrieved chunks using CrossEncoder.

    Args:
        query: The original query/category string used for retrieval
        chunks: List of chunk dicts from the retriever
        top_n: Number of top chunks to return (defaults to config.RERANKER_TOP_N)

    Returns:
        Reranked and trimmed list of chunks
    """
    if top_n is None:
        top_n = config.RERANKER_TOP_N

    if not chunks:
        return chunks

    reranker = _get_reranker()

    if reranker is not None:
        # ── CrossEncoder reranking ─────────────────────────────────────────────
        logger.info(f"Reranking {len(chunks)} chunks with CrossEncoder")
        pairs = [(query, c["text"]) for c in chunks]
        scores = reranker.predict(pairs)

        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = float(score)

        chunks = sorted(chunks, key=lambda c: c["rerank_score"], reverse=True)
        logger.info(f"Reranking complete. Top score: {chunks[0]['rerank_score']:.4f}")

    else:
        # ── Fallback: sort by original retrieval distance ──────────────────────
        logger.info("Using fallback distance-based ranking")
        chunks = sorted(chunks, key=lambda c: c.get("distance", 1.0))

    return chunks[:top_n]
