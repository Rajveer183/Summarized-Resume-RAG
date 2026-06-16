"""
FastAPI routes for resume accuracy evaluation.
"""
import traceback

from fastapi import APIRouter, HTTPException, Query

from backend.app.api.schemas import AccuracyReportResponse, EvaluateAllResponse
from backend.app.utils.file_utils import list_categories
from backend.evaluation.cache import get_cache_status, load_category_cache
from backend.evaluation._utils import public_category_report
from backend.evaluation.evaluate import (
    _resolve_data_path,
    evaluate_all_categories,
    evaluate_category,
    load_all_categories_report,
    load_latest_report,
    save_report,
)
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Evaluation"])


# Registered before /evaluate/{category} so "all" is not captured as a category name.
@router.get("/evaluate/all", response_model=EvaluateAllResponse)
async def evaluate_all(
    regenerate: bool = Query(
        False,
        description="Regenerate resumes for every category before evaluation",
    ),
    force_refresh: bool = Query(
        False,
        description="Ignore cache and recompute all 24 category scores",
    ),
):
    """Evaluate accuracy for all categories (served from cache when available)."""
    try:
        report = evaluate_all_categories(
            regenerate=regenerate, force_refresh=force_refresh
        )
        summary = report.get("summary", {})
        save_report(
            {
                "category": "ALL",
                **summary,
                "evaluated_at": report.get("evaluated_at"),
            },
        )
        return report
    except Exception as e:
        logger.error(f"Evaluate-all failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Evaluate-all failed: {e}")


@router.get("/evaluate/{category}", response_model=AccuracyReportResponse)
async def evaluate_single_category(
    category: str,
    regenerate: bool = Query(
        False,
        description="Force new LLM resume generation instead of using cached PDF",
    ),
    force_refresh: bool = Query(
        False,
        description="Ignore cache and recompute accuracy for this category",
    ),
):
    """Evaluate accuracy for one resume category."""
    category_key = category.strip().upper()
    if category_key == "ALL":
        raise HTTPException(
            status_code=400,
            detail="Use GET /evaluate/all to evaluate all categories.",
        )
    available = list_categories(_resolve_data_path())
    if category_key not in available:
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category_key}' not found. Available: {available}",
        )
    try:
        report = evaluate_category(
            category_key,
            regenerate=regenerate,
            force_refresh=force_refresh,
        )
        if not report.get("from_cache"):
            save_report(report)
        return report
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Evaluation failed: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Evaluation failed: {e}")


@router.get("/accuracy/report", response_model=AccuracyReportResponse)
async def get_accuracy_report():
    """Return the latest accuracy report (single category or aggregate summary)."""
    report = load_latest_report()
    if not report:
        raise HTTPException(
            status_code=404,
            detail="No accuracy report found. Run GET /evaluate/{category} first.",
        )
    if "retrieval_accuracy" not in report and report.get("summary"):
        report = {"category": "ALL", **report["summary"]}
    return report


@router.get("/accuracy/report/all", response_model=EvaluateAllResponse)
async def get_all_accuracy_report():
    """Return cached evaluate-all report (instant; no re-evaluation)."""
    report = load_all_categories_report()
    if not report or not report.get("categories"):
        raise HTTPException(
            status_code=404,
            detail="No cached accuracy report found. Run GET /evaluate/all once to build cache.",
        )
    return report


@router.get("/accuracy/cache/status")
async def get_accuracy_cache_status():
    """Whether a cached all-categories accuracy report is available."""
    data_path = _resolve_data_path()
    categories = list_categories(data_path)
    return get_cache_status(len(categories))


@router.get("/accuracy/cache/{category}", response_model=AccuracyReportResponse)
async def get_category_cached_report(category: str):
    """Return cached accuracy for one category without re-running evaluation."""
    category_key = category.strip().upper()
    cached = load_category_cache(category_key)
    if not cached:
        raise HTTPException(
            status_code=404,
            detail=f"No cached report for '{category_key}'. Evaluate this category first.",
        )
    return public_category_report(cached)
