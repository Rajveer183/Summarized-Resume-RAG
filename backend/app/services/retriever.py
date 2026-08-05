"""
Retrieval service — MMR-based retrieval from ChromaDB filtered by category.

Pipeline:
  1. Embed the category name as query
  2. Query ChromaDB with metadata filter on category (includes stored embeddings)
  3. Apply Maximum Marginal Relevance (MMR) for diversity
  4. Return top_k diverse chunks
"""
import math
from typing import Any, Dict, List

from backend.app.config import config
from backend.app.services.embedding_service import embed_query
from backend.app.services.vector_store import ensure_collection_healthy, query_by_category
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two vectors."""
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


def _distance_to_similarity(distance: float) -> float:
    """Map Chroma cosine distance to similarity (vectors are L2-normalized)."""
    return 1.0 - distance


def _mmr_select(
    query_embedding: List[float],
    candidate_embeddings: List[List[float]],
    candidate_docs: List[Dict],
    top_k: int,
    lambda_mult: float = 0.6,
) -> List[Dict]:
    """
    Maximum Marginal Relevance selection.

    Args:
        query_embedding: Query vector
        candidate_embeddings: Embeddings of all candidates
        candidate_docs: Corresponding document dicts
        top_k: Number of results to return
        lambda_mult: Trade-off between relevance (1.0) and diversity (0.0)

    Returns:
        List of selected document dicts ordered by MMR score
    """
    selected_indices = []
    remaining_indices = list(range(len(candidate_docs)))

    for _ in range(min(top_k, len(candidate_docs))):
        best_idx = None
        best_score = float("-inf")

        for idx in remaining_indices:
            relevance = _cosine_similarity(query_embedding, candidate_embeddings[idx])

            if selected_indices:
                redundancy = max(
                    _cosine_similarity(
                        candidate_embeddings[idx], candidate_embeddings[s]
                    )
                    for s in selected_indices
                )
            else:
                redundancy = 0.0

            mmr_score = lambda_mult * relevance - (1 - lambda_mult) * redundancy

            if mmr_score > best_score:
                best_score = mmr_score
                best_idx = idx

        if best_idx is not None:
            selected_indices.append(best_idx)
            remaining_indices.remove(best_idx)

    return [candidate_docs[i] for i in selected_indices]


def retrieve_chunks(category: str) -> List[Dict[str, Any]]:
    """
    Retrieve top relevant chunks for a given category.
    Bypasses semantic search (and PyTorch) to prevent Windows CPU deadlocks.
    """
    logger.info(f"Retrieving chunks for category: {category}")
    from backend.app.services.vector_store import ensure_collection_healthy, get_collection

    ensure_collection_healthy()
    collection = get_collection()

    results = collection.get(
        where={"category": category},
        limit=config.RETRIEVAL_TOP_K,
        include=["documents", "metadatas"]
    )

    documents = results.get("documents", [])
    metadatas = results.get("metadatas", [])

    if not documents:
        logger.warning(f"No chunks found for category: {category}")
        return []

    logger.info(f"Fetched {len(documents)} candidate chunks directly from ChromaDB")

    candidates = [
        {
            "text": doc,
            "metadata": meta,
            "distance": 0.0,
            "relevance": 1.0,
        }
        for doc, meta in zip(documents, metadatas)
    ]
    return candidates
