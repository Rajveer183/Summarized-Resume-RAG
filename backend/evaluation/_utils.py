"""Shared helpers for accuracy evaluation modules."""
from typing import Union


WEIGHTS = {
    "retrieval": 0.30,
    "category": 0.25,
    "content": 0.30,
    "privacy": 0.15,
}


def clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


def format_percent(value: float) -> str:
    return f"{round(clamp_percent(value), 1)}%"


def parse_percent(value: Union[str, float, int]) -> float:
    if isinstance(value, str):
        return float(value.replace("%", "").strip())
    return float(value)


def compute_overall_accuracy(
    retrieval: float,
    category: float,
    content: float,
    privacy: float,
) -> float:
    return (
        retrieval * WEIGHTS["retrieval"]
        + category * WEIGHTS["category"]
        + content * WEIGHTS["content"]
        + privacy * WEIGHTS["privacy"]
    )


PUBLIC_CATEGORY_KEYS = frozenset(
    {
        "category",
        "retrieval_accuracy",
        "category_accuracy",
        "content_accuracy",
        "privacy_accuracy",
        "overall_accuracy",
        "evaluated_at",
        "error",
    }
)

PUBLIC_SUMMARY_KEYS = frozenset(
    {
        "retrieval_accuracy",
        "category_accuracy",
        "content_accuracy",
        "privacy_accuracy",
        "overall_accuracy",
    }
)


def public_category_report(report: dict) -> dict:
    """Strip internal-only fields before API responses."""
    if not report:
        return report
    return {k: report[k] for k in PUBLIC_CATEGORY_KEYS if k in report}


def public_evaluate_all_report(report: dict) -> dict:
    """Strip internal-only fields from evaluate-all payloads."""
    if not report:
        return report
    out = {
        k: report[k]
        for k in ("evaluated_at", "total_categories")
        if k in report
    }
    if "categories" in report:
        out["categories"] = [public_category_report(c) for c in report["categories"]]
    if "summary" in report and report["summary"]:
        out["summary"] = {
            k: report["summary"][k]
            for k in PUBLIC_SUMMARY_KEYS
            if k in report["summary"]
        }
    return out
