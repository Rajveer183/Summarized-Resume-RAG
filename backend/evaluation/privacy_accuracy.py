"""
Privacy accuracy — detects PII leakage in generated resumes.
"""
import re
from typing import List, Tuple

from backend.evaluation._utils import clamp_percent

_ALLOWED_LITERALS = {
    "candidate",
    "[email]",
    "[phone]",
    "[url]",
    "xyz company",
    "abc company",
    "def company",
    "xyz university",
    "available for opportunities",
}

_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}\b",
    re.I,
)
_PHONE_RE = re.compile(
    r"(?<!\[)\+?\d{1,3}[\s\-.]?\(?\d{2,4}\)?[\s\-.]?\d{3,5}[\s\-.]?\d{4,6}\b",
)
_LINKEDIN_RE = re.compile(r"linkedin\.com", re.I)
_GITHUB_RE = re.compile(r"github\.com", re.I)
_URL_RE = re.compile(r"\bhttps?://\S+|\bwww\.\S+", re.I)
_ADDRESS_RE = re.compile(
    r"\d{1,5}\s+\w+\s+(street|st|avenue|ave|road|rd|boulevard|blvd|lane|ln|drive|dr)\b",
    re.I,
)
_REAL_NAME_RE = re.compile(
    r"\b(?!Candidate\b)(?!Professional\b)(?!XYZ\b)(?!ABC\b)(?!DEF\b)"
    r"(?!Available\b)(?!Opportunities\b)"
    r"[A-Z][a-z]+\s+[A-Z][a-z]+\b"
)

# Common real university / company indicators (not placeholders)
_FORBIDDEN_ORG_RE = re.compile(
    r"\b(inc\.?|llc|ltd|corp\.?|university of|institute of technology|"
    r"google|microsoft|amazon|facebook|meta)\b",
    re.I,
)

_PII_CHECKS: List[Tuple[str, re.Pattern]] = [
    ("email", _EMAIL_RE),
    ("phone", _PHONE_RE),
    ("linkedin", _LINKEDIN_RE),
    ("github", _GITHUB_RE),
    ("url", _URL_RE),
    ("address", _ADDRESS_RE),
    ("suspected_name", _REAL_NAME_RE),
    ("real_organization", _FORBIDDEN_ORG_RE),
]

_PENALTY_PER_LEAK = 12.5  # 8 leak types → 100 max penalty


def _is_allowed_match(match: str) -> bool:
    lowered = match.lower().strip()
    return any(a in lowered for a in _ALLOWED_LITERALS if a not in ("[email]", "[phone]", "[url]"))


def detect_pii_leaks(resume_text: str) -> List[str]:
    leaks: List[str] = []
    for label, pattern in _PII_CHECKS:
        for match in pattern.findall(resume_text):
            token = match if isinstance(match, str) else " ".join(match)
            if label == "email" and token.upper() == "[EMAIL]":
                continue
            if label == "phone" and "[PHONE]" in resume_text.upper():
                continue
            if label == "url" and "[URL]" in resume_text.upper():
                continue
            if label == "suspected_name" and token.lower() in (
                "candidate",
                "professional summary",
                "technical skills",
                "work experience",
            ):
                continue
            if label == "url" and "[url]" in resume_text.lower():
                continue
            if _is_allowed_match(token):
                continue
            leaks.append(label)
            break
    return leaks


def compute_privacy_accuracy(resume_text: str) -> float:
    """Privacy Accuracy = 100 - PII leakage penalty."""
    leaks = detect_pii_leaks(resume_text)
    penalty = len(leaks) * _PENALTY_PER_LEAK
    return clamp_percent(100.0 - penalty)
