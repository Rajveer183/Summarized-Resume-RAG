"""
Optimized ingestion pipeline — shared by ingest.py and the /ingest API route.

Targets ~15 minutes for the full dataset (~2.5k PDFs) via:
  - parallel PDF extraction
  - large embedding batches
  - large Chroma upsert batches
"""
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.config import config
from backend.app.services.chunker import chunk_resume
from backend.app.services.embedding_service import embed_texts, warmup_embedding_model
from backend.app.services.pdf_loader import load_pdf
from backend.app.services.pii_cleaner import clean_pii
from backend.app.services.vector_store import (
    ensure_collection_healthy,
    get_collection_stats,
    reset_collection,
    upsert_chunks,
)
from backend.app.utils.file_utils import list_categories, list_pdfs
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def _process_single_pdf(
    pdf_path: Path, category: str
) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """Extract, clean, and chunk one PDF. Returns (chunks, error_message)."""
    try:
        text = load_pdf(pdf_path)
        if not text or len(text.strip()) < 50:
            return None, f"Empty: {pdf_path.name}"
        clean_text = clean_pii(text)
        chunks = chunk_resume(
            text=clean_text,
            category=category,
            source_file=pdf_path.name,
        )
        return chunks, None
    except Exception as e:
        return None, f"{pdf_path.name}: {e}"


def ingest_category(category: str) -> dict:
    """Full ingestion pipeline for a single category."""
    category_path = config.DATA_PATH / category
    pdfs = list_pdfs(category_path)

    stats = {
        "pdfs_total": len(pdfs),
        "pdfs_processed": 0,
        "chunks_created": 0,
        "errors": [],
    }

    if not pdfs:
        return stats

    all_chunks: List[Dict[str, Any]] = []
    workers = min(config.INGEST_PDF_WORKERS, len(pdfs))

    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(_process_single_pdf, pdf_path, category): pdf_path
            for pdf_path in pdfs
        }
        for future in as_completed(futures):
            chunks, error = future.result()
            if error:
                stats["errors"].append(error)
                if chunks is None and error.startswith("Empty:"):
                    logger.debug(f"  Skipping: {error}")
                else:
                    logger.error(f"  ✗ {error}")
                continue
            if chunks:
                all_chunks.extend(chunks)
                stats["pdfs_processed"] += 1

    if not all_chunks:
        logger.warning(f"  No chunks generated for category: {category}")
        return stats

    logger.info(f"  Embedding {len(all_chunks)} chunks...")
    batch_count = 0
    upsert_batch = config.INGEST_UPSERT_BATCH_SIZE

    for i in range(0, len(all_chunks), upsert_batch):
        batch = all_chunks[i : i + upsert_batch]
        texts = [c["text"] for c in batch]
        try:
            embeddings = embed_texts(texts)
            upsert_chunks(batch, embeddings)
            batch_count += len(batch)
        except Exception as e:
            logger.error(f"  Batch embedding/upsert failed at {i}: {e}")
            stats["errors"].append(f"Batch {i}-{i + upsert_batch}: {e}")

    stats["chunks_created"] = batch_count
    return stats


def run_ingestion(reset_db: Optional[bool] = None) -> Dict[str, Any]:
    """
    Run the full dataset ingestion pipeline.

    Args:
        reset_db: Wipe Chroma collection before ingest. Defaults to config.INGEST_RESET_DB.

    Returns:
        Summary statistics dict.
    """
    if reset_db is None:
        reset_db = config.INGEST_RESET_DB

    start_time = time.time()

    if not config.DATA_PATH.exists():
        raise FileNotFoundError(f"Data path not found: {config.DATA_PATH}")

    ensure_collection_healthy()
    logger.info("Pre-loading embedding model...")
    warmup_embedding_model()

    if reset_db:
        logger.warning("Resetting ChromaDB collection before ingest...")
        reset_collection()

    categories = list_categories(config.DATA_PATH)
    if not categories:
        raise RuntimeError("No category directories found under data path")

    global_stats = {
        "total_categories": len(categories),
        "total_pdfs": 0,
        "total_chunks": 0,
        "failed_categories": [],
        "elapsed_seconds": 0.0,
    }

    for idx, category in enumerate(categories, 1):
        logger.info(f"[{idx:02d}/{len(categories)}] Processing: {category}")
        cat_start = time.time()
        stats = ingest_category(category)
        elapsed = time.time() - cat_start
        logger.info(
            f"  ✓ Done: {stats['pdfs_processed']}/{stats['pdfs_total']} PDFs, "
            f"{stats['chunks_created']} chunks  [{elapsed:.1f}s]"
        )
        if stats["errors"]:
            logger.warning(f"  Errors: {len(stats['errors'])}")
        global_stats["total_pdfs"] += stats["pdfs_processed"]
        global_stats["total_chunks"] += stats["chunks_created"]
        if stats["pdfs_processed"] == 0 and stats["pdfs_total"] > 0:
            global_stats["failed_categories"].append(category)

    global_stats["elapsed_seconds"] = time.time() - start_time
    global_stats["chroma_stats"] = get_collection_stats()
    return global_stats
