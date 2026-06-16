"""
Accuracy evaluation orchestrator — runs all metrics and writes JSON reports.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.app.config import config
from backend.app.services.retriever import retrieve_chunks
from backend.app.services.resume_generator import generate_resume
from backend.app.utils.file_utils import list_categories
from backend.app.utils.logger import get_logger
from backend.evaluation._utils import (
    compute_overall_accuracy,
    format_percent,
    public_category_report,
    public_evaluate_all_report,
)
from backend.evaluation.category_accuracy import compute_category_accuracy
from backend.evaluation.content_accuracy import compute_content_accuracy
from backend.evaluation.privacy_accuracy import compute_privacy_accuracy
from backend.evaluation.retrieval_accuracy import (
    compute_retrieval_accuracy,
    fetch_retrieved_chunks,
)

logger = get_logger(__name__)

from backend.evaluation.cache import (
    load_all_categories_cache,
    load_category_cache,
    save_all_categories_cache,
    save_category_cache,
)

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORT_FILE = REPORTS_DIR / "report.json"
REPORT_ALL_FILE = REPORTS_DIR / "report_all.json"


def _resolve_data_path() -> Path:
    """Return configured resume dataset path."""
    return config.DATA_PATH


def _find_latest_resume_text(category: str) -> Optional[str]:
    """Load newest saved resume text (.txt sidecar preferred, else PDF extract)."""
    safe = category.replace(" ", "_")
    txts = sorted(
        config.GENERATED_RESUMES_PATH.glob(f"resume_{safe}*.txt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if txts:
        try:
            text = txts[0].read_text(encoding="utf-8").strip()
            if len(text) > 100:
                return text
        except Exception as e:
            logger.debug(f"Could not read resume txt for {category}: {e}")

    pattern = f"resume_{safe}*.pdf"
    pdfs = sorted(
        config.GENERATED_RESUMES_PATH.glob(pattern),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not pdfs:
        return None
    try:
        import fitz

        doc = fitz.open(str(pdfs[0]))
        pages = [page.get_text("text") for page in doc]
        doc.close()
        text = "\n".join(pages).strip()
        return text if len(text) > 100 else None
    except Exception as e:
        logger.debug(f"Could not read PDF for {category}: {e}")
        return None


def _get_resume_text(category: str, resume_text: Optional[str], regenerate: bool) -> str:
    if resume_text and resume_text.strip():
        return resume_text
    if not regenerate:
        cached = _find_latest_resume_text(category)
        if cached:
            logger.info(f"Using cached generated PDF text for {category}")
            return cached
    logger.info(f"Generating resume for evaluation: {category}")
    result = generate_resume(category)
    return result["resume_text"]


def evaluate_category(
    category: str,
    *,
    resume_text: Optional[str] = None,
    regenerate: bool = False,
    force_refresh: bool = False,
) -> Dict[str, Any]:
    """
    Run full accuracy evaluation for one category using real retrieval and resumes.
    Returns cached result when available unless force_refresh or regenerate is True.
    """
    category_key = category.strip().upper()

    if not force_refresh and not regenerate and resume_text is None:
        cached = load_category_cache(category_key)
        if cached:
            logger.info(f"Returning cached accuracy for {category_key}")
            return public_category_report(dict(cached))

    data_path = _resolve_data_path()
    categories = list_categories(data_path)
    if category_key not in categories:
        raise ValueError(
            f"Category '{category_key}' not found. Available: {categories}"
        )

    retrieved_chunks = fetch_retrieved_chunks(category_key)
    mmr_chunks = retrieve_chunks(category_key)
    context_chunks = mmr_chunks if mmr_chunks else retrieved_chunks

    text = _get_resume_text(category_key, resume_text, regenerate)

    retrieval = compute_retrieval_accuracy(category_key, retrieved_chunks)
    category_acc = compute_category_accuracy(category_key, text, categories)
    content = compute_content_accuracy(text, context_chunks)
    privacy = compute_privacy_accuracy(text)

    overall = compute_overall_accuracy(retrieval, category_acc, content, privacy)

    report = {
        "category": category_key,
        "retrieval_accuracy": format_percent(retrieval),
        "category_accuracy": format_percent(category_acc),
        "content_accuracy": format_percent(content),
        "privacy_accuracy": format_percent(privacy),
        "overall_accuracy": format_percent(overall),
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
    }
    save_category_cache(report)
    return report


def save_report(report: Dict[str, Any], *, all_categories: bool = False) -> Path:
    if all_categories:
        return save_all_categories_cache(report)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=4)
    return REPORT_FILE


def load_latest_report() -> Dict[str, Any]:
    if REPORT_FILE.exists():
        with open(REPORT_FILE, encoding="utf-8") as f:
            return public_category_report(json.load(f))
    if REPORT_ALL_FILE.exists():
        with open(REPORT_ALL_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if "latest_single" in data:
            return public_category_report(data["latest_single"])
        if data.get("categories"):
            return public_category_report(data["categories"][0])
    return {}


def load_all_categories_report() -> Dict[str, Any]:
    """Load the full evaluate-all report with per-category breakdown."""
    data_path = _resolve_data_path()
    expected = len(list_categories(data_path)) or None
    cached = load_all_categories_cache(expected_count=expected)
    return public_evaluate_all_report(cached or {})


def evaluate_all_categories(
    *, regenerate: bool = False, force_refresh: bool = False
) -> Dict[str, Any]:
    """Evaluate all categories and produce aggregate report."""
    data_path = _resolve_data_path()
    categories = list_categories(data_path)
    if not categories:
        raise RuntimeError(f"No categories found at {data_path}")

    if not force_refresh and not regenerate:
        cached = load_all_categories_cache(expected_count=len(categories))
        if cached:
            logger.info(
                f"Returning cached all-categories report "
                f"({len(categories)} categories)"
            )
            return public_evaluate_all_report(cached)

    category_reports: List[Dict[str, Any]] = []
    totals = {
        "retrieval": 0.0,
        "category": 0.0,
        "content": 0.0,
        "privacy": 0.0,
        "overall": 0.0,
    }

    for cat in categories:
        logger.info(f"Evaluating category: {cat}")
        try:
            report = evaluate_category(cat, regenerate=regenerate)
            category_reports.append(report)
            totals["retrieval"] += float(report["retrieval_accuracy"].rstrip("%"))
            totals["category"] += float(report["category_accuracy"].rstrip("%"))
            totals["content"] += float(report["content_accuracy"].rstrip("%"))
            totals["privacy"] += float(report["privacy_accuracy"].rstrip("%"))
            totals["overall"] += float(report["overall_accuracy"].rstrip("%"))
        except Exception as e:
            logger.error(f"Evaluation failed for {cat}: {e}")
            category_reports.append(
                {
                    "category": cat,
                    "error": str(e),
                }
            )

    successful = [r for r in category_reports if "overall_accuracy" in r]
    n = max(len(successful), 1)
    if successful:
        totals = {k: 0.0 for k in totals}
        for report in successful:
            totals["retrieval"] += float(report["retrieval_accuracy"].rstrip("%"))
            totals["category"] += float(report["category_accuracy"].rstrip("%"))
            totals["content"] += float(report["content_accuracy"].rstrip("%"))
            totals["privacy"] += float(report["privacy_accuracy"].rstrip("%"))
            totals["overall"] += float(report["overall_accuracy"].rstrip("%"))

    aggregate = {
        "categories": category_reports,
        "summary": {
            "retrieval_accuracy": format_percent(totals["retrieval"] / n),
            "category_accuracy": format_percent(totals["category"] / n),
            "content_accuracy": format_percent(totals["content"] / n),
            "privacy_accuracy": format_percent(totals["privacy"] / n),
            "overall_accuracy": format_percent(totals["overall"] / n),
        },
        "evaluated_at": datetime.utcnow().isoformat() + "Z",
        "total_categories": len(categories),
    }

    if category_reports and "overall_accuracy" in category_reports[0]:
        aggregate["latest_single"] = category_reports[0]

    save_all_categories_cache(aggregate)
    if category_reports and "overall_accuracy" in category_reports[-1]:
        save_report(category_reports[-1])
    return aggregate
