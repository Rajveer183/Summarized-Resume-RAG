"""
Vector store service — manages ChromaDB collection for resume chunks.
Collection: resume_chunks
Persist path: backend/chroma_db/
"""
import re
from typing import Any, Dict, List, Optional

import chromadb
from chromadb.config import Settings

from backend.app.config import config
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

_client: Optional[chromadb.PersistentClient] = None
_collection = None

_HNSW_CORRUPTION_RE = re.compile(
    r"hnsw|segment reader|backfill request to compactor|loading hnsw index",
    re.IGNORECASE,
)

_COLLECTION_METADATA = {
    "hnsw:space": "cosine",
    # Faster index build during bulk ingest (defaults are higher = slower)
    "hnsw:construction_ef": 64,
    "hnsw:M": 16,
}


def is_hnsw_corruption_error(exc: BaseException) -> bool:
    """Return True when Chroma failed due to a corrupt or incomplete HNSW index."""
    return bool(_HNSW_CORRUPTION_RE.search(str(exc)))


def _chroma_settings() -> Settings:
    return Settings(
        anonymized_telemetry=False,
        allow_reset=True,
        is_persistent=True,
    )


def _get_client() -> chromadb.PersistentClient:
    """Lazy-initialize and return the ChromaDB persistent client."""
    global _client
    if _client is None:
        persist_path = str(config.CHROMA_PERSIST_PATH)
        logger.info(f"Initializing ChromaDB client at: {persist_path}")
        _client = chromadb.PersistentClient(
            path=persist_path,
            settings=_chroma_settings(),
        )
        logger.info("ChromaDB client initialized")
    return _client


def _invalidate_collection_cache() -> None:
    global _collection
    _collection = None


def repair_corrupted_collection() -> None:
    """
    Drop and recreate the collection when the on-disk HNSW index is corrupt.
    Typically caused by interrupted ingestion or a version mismatch.
    """
    client = _get_client()
    _invalidate_collection_cache()
    try:
        client.delete_collection(config.CHROMA_COLLECTION)
        logger.warning(f"Deleted corrupt collection: {config.CHROMA_COLLECTION}")
    except Exception as e:
        logger.debug(f"Collection delete skipped: {e}")
    get_collection()


def _probe_collection(collection) -> None:
    """Raise if the collection or its vector index cannot be read."""
    if collection.count() == 0:
        return
    # Minimal query to verify the HNSW segment is loadable
    collection.peek(limit=1)
    sample = collection.get(limit=1, include=["embeddings"])
    raw_embeddings = sample.get("embeddings")
    if raw_embeddings is None or len(raw_embeddings) == 0:
        return
    first = raw_embeddings[0]
    if first is None:
        return
    dim = len(first)
    collection.query(
        query_embeddings=[[0.0] * dim],
        n_results=1,
        include=["documents"],
    )


def ensure_collection_healthy() -> bool:
    """
    Verify ChromaDB is usable; auto-repair corrupt HNSW indexes.

    Returns:
        True if healthy (possibly after repair), False if repair failed.
    """
    try:
        collection = get_collection()
        _probe_collection(collection)
        return True
    except Exception as e:
        if not is_hnsw_corruption_error(e):
            logger.error(f"ChromaDB health check failed: {e}")
            return False
        logger.warning(
            "Corrupt ChromaDB HNSW index detected (often from interrupted ingest). "
            "Repairing collection — re-run ingestion: python backend/ingest.py"
        )
        try:
            repair_corrupted_collection()
            _probe_collection(get_collection())
            return True
        except Exception as repair_err:
            logger.error(f"ChromaDB repair failed: {repair_err}")
            return False


def get_collection():
    """Get or create the resume_chunks ChromaDB collection."""
    global _collection
    if _collection is not None:
        return _collection

    client = _get_client()
    try:
        _collection = client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            metadata=_COLLECTION_METADATA,
        )
        _probe_collection(_collection)
        logger.info(
            f"Collection '{config.CHROMA_COLLECTION}' ready "
            f"({_collection.count()} existing chunks)"
        )
    except Exception as e:
        if not is_hnsw_corruption_error(e):
            raise
        logger.warning(f"Collection open failed ({e}); attempting repair...")
        repair_corrupted_collection()
        _collection = client.get_or_create_collection(
            name=config.CHROMA_COLLECTION,
            metadata=_COLLECTION_METADATA,
        )
        logger.info(
            f"Collection '{config.CHROMA_COLLECTION}' recreated after repair"
        )
    return _collection


def upsert_chunks(chunks: List[Dict[str, Any]], embeddings: List[List[float]]) -> int:
    """
    Upsert chunks into ChromaDB with their embeddings and metadata.

    Args:
        chunks: List of chunk dicts with 'text' and 'metadata' keys
        embeddings: Corresponding list of embedding vectors

    Returns:
        Number of chunks upserted
    """
    if not chunks:
        return 0

    collection = get_collection()

    ids = [c["metadata"]["chunk_id"] for c in chunks]
    documents = [c["text"] for c in chunks]
    metadatas = [c["metadata"] for c in chunks]

    collection.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    return len(chunks)


def query_by_category(
    query_embedding: List[float],
    category: str,
    n_results: int = 30,
) -> Dict[str, Any]:
    """
    Query ChromaDB filtered by category metadata.

    Args:
        query_embedding: Query vector
        category: Resume category to filter by
        n_results: Number of results to retrieve

    Returns:
        ChromaDB query results dict (includes embeddings for MMR)
    """
    collection = get_collection()

    total = collection.count()
    if total == 0:
        logger.warning("ChromaDB collection is empty — run ingestion first")
        return {
            "documents": [[]],
            "metadatas": [[]],
            "distances": [[]],
            "embeddings": [[]],
        }

    return collection.query(
        query_embeddings=[query_embedding],
        n_results=min(n_results, total),
        where={"category": category},
        include=["documents", "metadatas", "distances", "embeddings"],
    )


def get_collection_stats() -> Dict[str, Any]:
    """Return statistics about the ChromaDB collection."""
    ensure_collection_healthy()
    collection = get_collection()
    total = collection.count()
    return {
        "total_chunks": total,
        "collection_name": config.CHROMA_COLLECTION,
        "persist_path": str(config.CHROMA_PERSIST_PATH),
    }


def reset_collection() -> None:
    """Delete and recreate the collection (use with caution)."""
    client = _get_client()
    _invalidate_collection_cache()
    try:
        client.delete_collection(config.CHROMA_COLLECTION)
        logger.warning(f"Deleted collection: {config.CHROMA_COLLECTION}")
    except Exception:
        pass
    get_collection()
