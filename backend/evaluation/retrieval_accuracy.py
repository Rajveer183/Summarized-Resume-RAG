"""
Retrieval accuracy — fraction of retrieved chunks from the selected category.
Uses real ChromaDB query (same embedding + filter as the RAG pipeline).
"""
from typing import Any, Dict, List

from backend.app.config import config
from backend.app.services.embedding_service import embed_query
from backend.app.services.vector_store import ensure_collection_healthy, query_by_category
from backend.evaluation._utils import clamp_percent


def fetch_retrieved_chunks(category: str) -> List[Dict[str, Any]]:
    """Fetch the candidate pool from ChromaDB (production fetch_k size)."""
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

    chunks = []
    for doc, meta, dist in zip(documents, metadatas, distances):
        chunks.append(
            {
                "text": doc,
                "metadata": meta or {},
                "distance": dist,
            }
        )
    return chunks


def compute_retrieval_accuracy(category: str, chunks: List[Dict[str, Any]] | None = None) -> float:
    """
    Retrieval Accuracy = correct_category_chunks / total_retrieved_chunks × 100
    """
    category_key = category.strip().upper()
    if chunks is None:
        chunks = fetch_retrieved_chunks(category_key)

    if not chunks:
        return 0.0

    correct = 0
    for chunk in chunks:
        meta_category = (chunk.get("metadata") or {}).get("category", "")
        if str(meta_category).strip().upper() == category_key:
            correct += 1

    return clamp_percent((correct / len(chunks)) * 100.0)
