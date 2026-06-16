"""
Persistent + in-memory cache for accuracy evaluation results.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORT_ALL_FILE = REPORTS_DIR / "report_all.json"
REPORT_FILE = REPORTS_DIR / "report.json"
CATEGORY_CACHE_DIR = REPORTS_DIR / "cache"

_memory_all_report: Optional[Dict[str, Any]] = None
_memory_all_mtime: float = 0.0
_memory_category: Dict[str, Dict[str, Any]] = {}


def _invalidate_memory() -> None:
    global _memory_all_report, _memory_all_mtime
    _memory_all_report = None
    _memory_all_mtime = 0.0
    _memory_category.clear()


def is_valid_category_report(report: Dict[str, Any]) -> bool:
    return bool(
        report
        and report.get("category")
        and report.get("retrieval_accuracy")
        and "error" not in report
    )


def is_valid_all_report(
    report: Dict[str, Any], expected_count: Optional[int] = None
) -> bool:
    if not report or not report.get("categories"):
        return False
    successful = [
        r for r in report["categories"] if is_valid_category_report(r)
    ]
    if expected_count is not None:
        return len(successful) >= expected_count
    return len(successful) >= 1


def save_category_cache(report: Dict[str, Any]) -> Path:
    """Persist one category's evaluation to disk."""
    CATEGORY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    category = report["category"]
    path = CATEGORY_CACHE_DIR / f"{category}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    _memory_category[category] = report
    logger.debug(f"Cached accuracy report for {category}")
    return path


def load_category_cache(category: str) -> Optional[Dict[str, Any]]:
    category_key = category.strip().upper()
    if category_key in _memory_category:
        return _memory_category[category_key]

    path = CATEGORY_CACHE_DIR / f"{category_key}.json"
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if is_valid_category_report(data):
            _memory_category[category_key] = data
            return data
    except Exception as e:
        logger.warning(f"Failed to read category cache {category_key}: {e}")
    return None


def save_all_categories_cache(report: Dict[str, Any]) -> Path:
    """Persist full 24-category report and refresh memory cache."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report = dict(report)
    report["cached_at"] = datetime.utcnow().isoformat() + "Z"
    report["from_cache"] = False

    with open(REPORT_ALL_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    global _memory_all_report, _memory_all_mtime
    _memory_all_report = report
    _memory_all_mtime = REPORT_ALL_FILE.stat().st_mtime

    for row in report.get("categories", []):
        if is_valid_category_report(row):
            save_category_cache(row)

    logger.info(
        f"Saved all-categories accuracy cache "
        f"({len(report.get('categories', []))} categories)"
    )
    return REPORT_ALL_FILE


def load_all_categories_cache(
    expected_count: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Load cached all-categories report from memory or disk."""
    global _memory_all_report, _memory_all_mtime

    if not REPORT_ALL_FILE.exists():
        return None

    mtime = REPORT_ALL_FILE.stat().st_mtime
    if _memory_all_report is not None and mtime == _memory_all_mtime:
        data = _memory_all_report
    else:
        try:
            with open(REPORT_ALL_FILE, encoding="utf-8") as f:
                data = json.load(f)
            _memory_all_report = data
            _memory_all_mtime = mtime
        except Exception as e:
            logger.warning(f"Failed to read all-categories cache: {e}")
            return None

    if not is_valid_all_report(data, expected_count=expected_count):
        return None

    for row in data.get("categories", []):
        if is_valid_category_report(row):
            cat = row["category"]
            cache_path = CATEGORY_CACHE_DIR / f"{cat}.json"
            if not cache_path.exists():
                save_category_cache(row)

    result = dict(data)
    result["from_cache"] = True
    if "cached_at" not in result and result.get("evaluated_at"):
        result["cached_at"] = result["evaluated_at"]
    return result


def get_cache_status(expected_count: int) -> Dict[str, Any]:
    """Metadata for UI — whether cached all-categories report is available."""
    cached = load_all_categories_cache(expected_count=expected_count)
    successful = 0
    if cached:
        successful = sum(
            1
            for r in cached.get("categories", [])
            if is_valid_category_report(r)
        )
    return {
        "all_categories_cached": cached is not None,
        "categories_cached": successful,
        "total_categories": expected_count,
        "cached_at": (cached or {}).get("cached_at") or (cached or {}).get("evaluated_at"),
        "cache_path": str(REPORT_ALL_FILE),
    }
