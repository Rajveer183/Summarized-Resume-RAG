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
    Retrieve top relevant and diverse chunks for a given category.

    Args:
        category: The resume category name (e.g., "INFORMATION-TECHNOLOGY")

    Returns:
        List of chunk dicts: {"text": str, "metadata": dict, "distance": float}
    """
    logger.info(f"Retrieving chunks for category: {category}")

    ensure_collection_healthy()

    query_text = (
        f"professional resume for {category.replace('-', ' ').lower()} "
        "role skills experience education"
    )
    query_embedding = embed_query(query_text)

    results = query_by_category(
        query_embedding=query_embedding,
        category=category,
        n_results=config.RETRIEVAL_FETCH_K,
    )

    documents = results.get("documents", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    distances = results.get("distances", [[]])[0]
    embeddings = results.get("embeddings", [[]])[0]

    if not documents:
        logger.warning(f"No chunks found for category: {category}")
        return []

    logger.info(f"Fetched {len(documents)} candidate chunks from ChromaDB")

    if embeddings is None or len(embeddings) == 0 or embeddings[0] is None:
        logger.warning("Chroma returned no embeddings; falling back to re-embed")
        from backend.app.services.embedding_service import embed_texts

        candidate_embeddings = embed_texts(documents)
    else:
        candidate_embeddings = [list(e) for e in embeddings]

    candidates = [
        {
            "text": doc,
            "metadata": meta,
            "distance": dist,
            "relevance": _distance_to_similarity(dist),
        }
        for doc, meta, dist in zip(documents, metadatas, distances)
    ]

    selected = _mmr_select(
        query_embedding=query_embedding,
        candidate_embeddings=candidate_embeddings,
        candidate_docs=candidates,
        top_k=config.RETRIEVAL_TOP_K,
    )

    logger.info(f"MMR selected {len(selected)} diverse chunks")

    sections = [c["metadata"].get("section_name", "Unknown") for c in selected]
    section_counts: Dict[str, int] = {}
    for s in sections:
        section_counts[s] = section_counts.get(s, 0) + 1
    logger.debug(f"Section distribution: {section_counts}")

    return selected
