"""
FastAPI routes for the Resume Generation RAG API.

Endpoints:
  GET  /health                 — Health check
  GET  /categories             — List all available categories
  POST /ingest                 — Run the full ingestion pipeline
  POST /generate-resume        — Generate a resume for a given category
  GET  /download/{filename}    — Download a generated PDF
"""
import traceback
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse

from backend.app.api.schemas import (
    CategoryListResponse,
    GenerateResumeRequest,
    GenerateResumeResponse,
    HealthResponse,
    IngestResponse,
)
from backend.app.config import config
from backend.app.services.pdf_generator import generate_pdf
from backend.app.services.resume_generator import generate_resume
from backend.app.utils.file_utils import list_categories
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()


# ── Health Check ───────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Backend health check — confirms the API is running."""
    return HealthResponse(
        status="ok",
        message="Resume API is running",
    )


# ── Categories ─────────────────────────────────────────────────────────────────

@router.get("/categories", response_model=CategoryListResponse, tags=["Resume"])
async def get_categories():
    """
    Return all available resume categories discovered from the data directory.
    Each category corresponds to a folder in data/data/.
    """
    categories = list_categories(config.DATA_PATH)
    if not categories:
        raise HTTPException(
            status_code=404,
            detail=f"No categories found in data path: {config.DATA_PATH}. "
                   "Ensure the dataset is correctly placed.",
        )
    return CategoryListResponse(categories=categories, total=len(categories))


# ── Ingestion ──────────────────────────────────────────────────────────────────

@router.post("/ingest", response_model=IngestResponse, tags=["System"])
async def run_ingestion(background_tasks: BackgroundTasks):
    """
    Trigger the full ingestion pipeline:
    Load PDFs → Clean PII → Chunk → Embed → Store in ChromaDB.

    This runs as a background task and returns immediately.
    For large datasets, check server logs for progress.
    """
    logger.info("Ingestion triggered via API")
    background_tasks.add_task(_run_ingest_task)
    return IngestResponse(
        status="started",
        message="Ingestion pipeline started in background. Check server logs for progress.",
        categories_processed=0,
        total_chunks=0,
    )


async def _run_ingest_task():
    """Background ingestion task."""
    try:
        from backend.app.services.ingest_service import run_ingestion

        stats = run_ingestion()
        logger.info(
            f"Ingestion finished: {stats['total_pdfs']} PDFs, "
            f"{stats['total_chunks']} chunks in {stats['elapsed_seconds']:.1f}s"
        )
    except Exception as e:
        logger.error(f"Ingestion task failed: {e}\n{traceback.format_exc()}")


# ── Generate Resume ────────────────────────────────────────────────────────────

@router.post("/generate-resume", response_model=GenerateResumeResponse, tags=["Resume"])
async def generate_resume_endpoint(request: GenerateResumeRequest):
    """
    Generate a professional anonymized resume for the given category.

    Pipeline:
      1. Retrieve relevant chunks from ChromaDB (filtered by category)
      2. Apply MMR retrieval + CrossEncoder reranking
      3. Call NVIDIA NIM LLM to generate resume text
      4. Convert to PDF and save
      5. Return resume text + PDF download URL

    Request body:
      { "category": "INFORMATION-TECHNOLOGY" }
    """
    category = request.category.strip().upper()
    logger.info(f"Resume generation request received: {category}")

    # Validate category exists
    available = list_categories(config.DATA_PATH)
    if category not in available:
        raise HTTPException(
            status_code=400,
            detail=f"Category '{category}' not found. Available: {available}",
        )

    # ── Generate resume text ──────────────────────────────────────────────────
    try:
        result = generate_resume(category)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"Resume generation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=f"Resume generation failed: {str(e)}",
        )

    resume_text = result["resume_text"]

    # ── Generate PDF ──────────────────────────────────────────────────────────
    pdf_path = None
    pdf_url = ""
    try:
        pdf_path = generate_pdf(resume_text, category)
        if pdf_path:
            pdf_url = f"/download/{pdf_path.name}"
            logger.info(f"PDF available at: {pdf_url}")
    except Exception as e:
        logger.error(f"PDF generation failed: {e}")
        pdf_url = ""  # Resume text still returned even if PDF fails

    return GenerateResumeResponse(
        category=category,
        resume_text=resume_text,
        pdf_url=pdf_url,
    )


# ── Download PDF ───────────────────────────────────────────────────────────────

@router.get("/download/{filename}", tags=["Resume"])
async def download_pdf(filename: str):
    """
    Download a previously generated resume PDF.
    Files are stored in backend/generated_resumes/.
    """
    # Security: prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    file_path = config.GENERATED_RESUMES_PATH / filename

    if not file_path.exists():
        raise HTTPException(
            status_code=404,
            detail=f"File '{filename}' not found. It may have expired or generation failed.",
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=filename,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
