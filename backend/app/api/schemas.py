"""Pydantic schemas for request/response validation."""
from typing import List, Optional
from pydantic import BaseModel, Field


class GenerateResumeRequest(BaseModel):
    """Request body for POST /generate-resume."""
    category: str = Field(
        ...,
        description="Resume category name (e.g., 'INFORMATION-TECHNOLOGY')",
        example="INFORMATION-TECHNOLOGY",
    )


class GenerateResumeResponse(BaseModel):
    """Response body for POST /generate-resume."""
    category: str
    resume_text: str
    pdf_url: str


class CategoryListResponse(BaseModel):
    """Response body for GET /categories."""
    categories: List[str]
    total: int


class HealthResponse(BaseModel):
    """Response body for GET /health."""
    status: str
    message: str
    version: str = "1.0.0"


class IngestResponse(BaseModel):
    """Response body for POST /ingest."""
    status: str
    message: str
    categories_processed: int
    total_chunks: int
    errors: List[str] = []


class ErrorResponse(BaseModel):
    """Standard error response."""
    error: str
    detail: Optional[str] = None


class AccuracyReportResponse(BaseModel):
    """Accuracy evaluation report for one category."""
    category: str
    retrieval_accuracy: str
    category_accuracy: str
    content_accuracy: str
    privacy_accuracy: str
    overall_accuracy: str
    evaluated_at: Optional[str] = None
    error: Optional[str] = None


class EvaluateAllSummary(BaseModel):
    retrieval_accuracy: str
    category_accuracy: str
    content_accuracy: str
    privacy_accuracy: str
    overall_accuracy: str


class EvaluateAllResponse(BaseModel):
    """Accuracy evaluation across all categories."""
    categories: List[dict]
    summary: EvaluateAllSummary
    evaluated_at: Optional[str] = None
    total_categories: int
