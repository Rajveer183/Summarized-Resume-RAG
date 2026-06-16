"""
PII Cleaner Service — removes/anonymizes personally identifiable information
from resume text before storing in the vector database.

Removed/replaced:
  - Candidate names (heuristic: capitalized words at top of doc)
  - Email addresses       → [EMAIL]
  - Phone numbers         → [PHONE]
  - LinkedIn URLs         → [URL]
  - GitHub URLs           → [URL]
  - Portfolio/personal URLs → [URL]
  - Physical addresses    → [ADDRESS]
  - All remaining name refs → Candidate
"""
import re
from typing import Optional

from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Compiled regex patterns ────────────────────────────────────────────────────

# Email
_EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Phone numbers (international + US formats)
_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s\-.]?)?"          # country code
    r"(\(?\d{2,4}\)?)?"               # area code
    r"[\s\-.]?"
    r"\d{3,5}"
    r"[\s\-.]?"
    r"\d{4,6}"
    r"(\s?(ext|x|ext\.)\s?\d{1,5})?", # extension
    re.IGNORECASE,
)

# LinkedIn URLs
_LINKEDIN_RE = re.compile(
    r"(https?://)?(www\.)?linkedin\.com/\S+",
    re.IGNORECASE,
)

# GitHub URLs
_GITHUB_RE = re.compile(
    r"(https?://)?(www\.)?github\.com/\S+",
    re.IGNORECASE,
)

# Generic URLs (http/https/www)
_URL_RE = re.compile(
    r"(https?://|www\.)\S+",
    re.IGNORECASE,
)

# Physical address patterns (e.g., "123 Main St, City, State 12345")
_ADDRESS_RE = re.compile(
    r"\d{1,5}\s+([A-Z][a-z]+\s+){1,3}"
    r"(Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|Circle|Cir|Way|Place|Pl)"
    r"[,\s]+[A-Za-z\s]+[,\s]+[A-Z]{2}\s+\d{5}(-\d{4})?",
    re.IGNORECASE,
)

# Name-like pattern: 2–4 capitalized words at the very start of the document
_NAME_AT_TOP_RE = re.compile(
    r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,3})\s*\n",
    re.MULTILINE,
)


def _remove_name_at_top(text: str) -> str:
    """
    Detect candidate name at the top of resume (first capitalized line)
    and replace all occurrences in the document with 'Candidate'.
    """
    match = _NAME_AT_TOP_RE.search(text[:500])  # only look in first 500 chars
    if match:
        name = match.group(1).strip()
        # Replace all occurrences of the name in the full text
        escaped = re.escape(name)
        text = re.sub(escaped, "Candidate", text, flags=re.IGNORECASE)
        logger.debug(f"Replaced name '{name}' with 'Candidate'")
    return text


def clean_pii(text: str) -> str:
    """
    Run all PII removal passes on the given resume text.
    Returns anonymized text safe for vector storage.
    """
    if not text:
        return text

    # 1. Remove candidate name from top of document
    text = _remove_name_at_top(text)

    # 2. Remove email addresses
    text = _EMAIL_RE.sub("[EMAIL]", text)

    # 3. Remove phone numbers (filter out short random digit matches)
    def _phone_replacer(m: re.Match) -> str:
        matched = m.group(0).strip()
        digits = re.sub(r"\D", "", matched)
        if len(digits) >= 7:  # valid phone length
            return "[PHONE]"
        return matched  # don't replace short numbers (e.g., years, page nums)

    text = _PHONE_RE.sub(_phone_replacer, text)

    # 4. Remove LinkedIn URLs
    text = _LINKEDIN_RE.sub("[URL]", text)

    # 5. Remove GitHub URLs
    text = _GITHUB_RE.sub("[URL]", text)

    # 6. Remove all remaining HTTP/HTTPS/WWW URLs
    text = _URL_RE.sub("[URL]", text)

    # 7. Remove physical addresses
    text = _ADDRESS_RE.sub("[ADDRESS]", text)

    # 8. Normalize whitespace artifacts
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = text.strip()

    return text
