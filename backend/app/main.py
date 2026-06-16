"""
FastAPI application factory for the Resume Generation RAG backend.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.evaluation_routes import router as evaluation_router
from backend.app.api.routes import router
from backend.app.config import config
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""

    app = FastAPI(
        title="Resume Generator API",
        description="Generate and evaluate professional resumes by job category.",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS Middleware ───────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            config.FRONTEND_ORIGIN,
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Include API routes ────────────────────────────────────────────────────
    app.include_router(router)
    app.include_router(evaluation_router)

    # ── Startup / Shutdown events ─────────────────────────────────────────────
    @app.on_event("startup")
    async def startup_event():
        logger.info("=" * 60)
        logger.info("Resume Generation RAG API starting up")
        logger.info(f"  Data path    : {config.DATA_PATH}")
        logger.info(f"  ChromaDB     : {config.CHROMA_PERSIST_PATH}")
        logger.info(f"  Output path  : {config.GENERATED_RESUMES_PATH}")
        logger.info(f"  NVIDIA model : {config.NVIDIA_MODEL}")
        logger.info(f"  Embed model  : {config.EMBEDDING_MODEL}")
        logger.info("=" * 60)

        # Ensure output directories exist
        config.ensure_dirs()

        # Warm up ChromaDB and auto-repair corrupt HNSW indexes
        try:
            from backend.app.services.vector_store import (
                ensure_collection_healthy,
                get_collection_stats,
            )

            if ensure_collection_healthy():
                stats = get_collection_stats()
                logger.info(f"ChromaDB connected: {stats['total_chunks']} chunks loaded")
                if stats["total_chunks"] == 0:
                    logger.warning(
                        "ChromaDB is empty! Run: python backend/ingest.py"
                    )
            else:
                logger.warning(
                    "ChromaDB is unhealthy. Set INGEST_RESET_DB=true and run: "
                    "python backend/ingest.py"
                )
        except Exception as e:
            logger.warning(f"ChromaDB warmup failed: {e}")

    @app.on_event("shutdown")
    async def shutdown_event():
        logger.info("Resume Generation RAG API shutting down")

    return app


# ── Application instance ──────────────────────────────────────────────────────
app = create_app()
