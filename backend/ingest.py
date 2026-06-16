"""
Standalone ingestion script — run ONCE to build the ChromaDB vector database.

Usage (from project root):
    python backend/ingest.py

Set INGEST_RESET_DB=true in .env to wipe and rebuild ChromaDB from scratch.
Target runtime: ~15 minutes for the full dataset (parallel PDF + batched embed).
"""
import sys
import time
from pathlib import Path

# ── Ensure project root is in sys.path ───────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.config import config
from backend.app.services.ingest_service import run_ingestion
from backend.app.utils.logger import get_logger

logger = get_logger("ingest")


def main():
    """Main ingestion entry point."""
    logger.info("=" * 65)
    logger.info("  RESUME RAG — INGESTION PIPELINE")
    logger.info("=" * 65)
    logger.info(f"  Data path         : {config.DATA_PATH}")
    logger.info(f"  ChromaDB          : {config.CHROMA_PERSIST_PATH}")
    logger.info(f"  Embed model       : {config.EMBEDDING_MODEL}")
    logger.info(f"  PDF workers       : {config.INGEST_PDF_WORKERS}")
    logger.info(f"  Embed batch size  : {config.INGEST_EMBED_BATCH_SIZE}")
    logger.info(f"  Upsert batch size : {config.INGEST_UPSERT_BATCH_SIZE}")
    logger.info(f"  Reset DB          : {config.INGEST_RESET_DB}")
    logger.info(f"  HF token set      : {bool(config.HF_TOKEN)}")
    logger.info("=" * 65)

    try:
        stats = run_ingestion()
    except FileNotFoundError as e:
        logger.error(str(e))
        logger.error("Ensure dataset is at data/data/ relative to project root")
        sys.exit(1)
    except RuntimeError as e:
        logger.error(str(e))
        sys.exit(1)

    elapsed = stats["elapsed_seconds"]
    chroma = stats.get("chroma_stats", {})

    logger.info("=" * 65)
    logger.info("  INGESTION COMPLETE")
    logger.info("=" * 65)
    logger.info(f"  Categories processed : {stats['total_categories']}")
    logger.info(f"  PDFs processed       : {stats['total_pdfs']}")
    logger.info(f"  Chunks created       : {stats['total_chunks']}")
    logger.info(f"  ChromaDB total       : {chroma.get('total_chunks', 0)}")
    logger.info(f"  Total time           : {elapsed:.1f}s ({elapsed / 60:.1f}min)")

    if stats["failed_categories"]:
        logger.warning(f"  Failed categories    : {stats['failed_categories']}")

    logger.info("=" * 65)
    logger.info("  You can now start the backend server:")
    logger.info("  uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000")
    logger.info("=" * 65)


if __name__ == "__main__":
    main()
