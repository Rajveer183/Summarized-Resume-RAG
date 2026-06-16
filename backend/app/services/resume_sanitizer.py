"""
Post-generation sanitization for resume text and structured fields.

Enforces anonymization, removes dates/experience years, and strips
seniority labels from titles before PDF rendering.
"""
import re
from typing import Any, Dict, List

from backend.app.utils.category_titles import get_professional_title

# Dates: years, ranges, month-year patterns
_DATE_PATTERNS = [
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}\b", re.I),
    re.compile(r"\b\d{4}\s*[-–—]\s*(?:Present|\d{4})\b", re.I),
    re.compile(r"\b(?:19|20)\d{2}\s*[-–—]\s*(?:Present|Current|\d{4})\b", re.I),
    re.compile(r"\b(?:19|20)\d{2}\b"),
]

_EXPERIENCE_YEARS_RE = re.compile(
    r"\b\d+\+?\s*(?:years?|yrs?)\s+(?:of\s+)?experience\b",
    re.I,
)

_SENIORITY_RE = re.compile(
    r"\b(?:Senior|Junior|Lead|Expert|Fresher|Intern|Entry[- ]Level)\b",
    re.I,
)

_EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", re.I)
_PHONE_RE = re.compile(
    r"(\+?\d{1,3}[\s\-.]?)?(\(?\d{2,4}\)?)?[\s\-.]?\d{3,5}[\s\-.]?\d{4,6}",
)
_URL_RE = re.compile(r"(https?://|www\.)\S+", re.I)
_LINKEDIN_RE = re.compile(r"(https?://)?(www\.)?linkedin\.com/\S+", re.I)
_GITHUB_RE = re.compile(r"(https?://)?(www\.)?github\.com/\S+", re.I)

_CANDIDATE_NAME_LINE_RE = re.compile(r"^candidate\s*$", re.I)
_CONTACT_PLACEHOLDER_RE = re.compile(
    r"^\[EMAIL\].*\[PHONE\].*\[URL\]|available for opportunities",
    re.I,
)

_PLACEHOLDER_COMPANIES = ("XYZ Company", "ABC Company", "DEF Company")
_PLACEHOLDER_UNIVERSITY = "XYZ University"
_GENERIC_CERTS = (
    "XYZ Certification",
    "XYZ Professional Certification",
    "XYZ Domain Certification",
)


def _strip_dates(text: str) -> str:
    if not text:
        return text
    for pattern in _DATE_PATTERNS:
        text = pattern.sub("", text)
    text = _EXPERIENCE_YEARS_RE.sub("", text)
    # Preserve line breaks (required for === section === parsing)
    lines = []
    for line in text.split("\n"):
        cleaned = re.sub(r"[ \t]{2,}", " ", line).strip()
        lines.append(cleaned)
    return "\n".join(lines)


def _normalize_pii_placeholders(text: str) -> str:
    text = _EMAIL_RE.sub("[EMAIL]", text)
    text = _LINKEDIN_RE.sub("[URL]", text)
    text = _GITHUB_RE.sub("[URL]", text)
    text = _URL_RE.sub("[URL]", text)

    def _phone_sub(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "[PHONE]" if len(digits) >= 7 else m.group(0)

    text = _PHONE_RE.sub(_phone_sub, text)
    return text


def _strip_header_noise(text: str) -> str:
    """Remove Candidate name line and contact placeholder line from LLM output."""
    kept: List[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped:
            kept.append(line)
            continue
        if _CANDIDATE_NAME_LINE_RE.match(stripped):
            continue
        if _CONTACT_PLACEHOLDER_RE.search(stripped):
            continue
        kept.append(line)
    return "\n".join(kept)


def sanitize_resume_text(resume_text: str, category: str) -> str:
    """Sanitize raw LLM resume output before parsing to PDF."""
    if not resume_text:
        return resume_text

    text = _normalize_pii_placeholders(resume_text)
    text = _strip_header_noise(text)
    text = _strip_dates(text)
    text = _SENIORITY_RE.sub("", text)

    # Force canonical header title in CANDIDATE TITLE section if present
    title = get_professional_title(category)
    text = re.sub(
        r"(===\s*CANDIDATE TITLE\s*===\s*\n)(.*?)(?=\n===)",
        rf"\1{title}\n",
        text,
        count=1,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return text.strip()


def enforce_resume_structure(resume_data: Dict[str, Any], category: str) -> Dict[str, Any]:
    """
    Enforce universal template placeholders and structure on parsed resume data.
    """
    resume_data["title"] = get_professional_title(category)
    resume_data["category"] = category

    # Skills: strip dates; ensure 3 subcategories with bullets
    skills: List[Dict[str, Any]] = []
    for group in resume_data.get("skills", []):
        category_name = _strip_dates(group.get("category", ""))
        if isinstance(group.get("items"), list):
            items = [_strip_dates(i) for i in group["items"] if i][:3]
        else:
            raw = _strip_dates(str(group.get("items", "")))
            items = [i.strip() for i in raw.split(",") if i.strip()][:3]
        if category_name or items:
            skills.append({"category": category_name or "Core Skills", "items": items})
    while len(skills) < 3:
        skills.append(
            {
                "category": ["Core Skills", "Tools & Technologies", "Professional Competencies"][
                    len(skills)
                ],
                "items": [
                    "Domain-relevant capability",
                    "Industry-standard practice",
                    "Professional methodology",
                ],
            }
        )
    for group in skills:
        while len(group["items"]) < 3:
            group["items"].append("Category-relevant professional skill")
    resume_data["skills"] = skills[:3]

    # Experience: fixed company names, no durations
    experience = resume_data.get("experience", [])[:3]
    normalized_exp: List[Dict[str, Any]] = []
    for idx, exp in enumerate(experience):
        company = _PLACEHOLDER_COMPANIES[idx] if idx < 3 else "XYZ Company"
        bullets = [
            _strip_dates(b) for b in exp.get("bullets", []) if b and len(b) > 10
        ][:4]
        if not bullets:
            bullets = [
                "Designed and implemented category-specific solutions following industry standards.",
                "Collaborated with teams to improve workflow and project delivery.",
                "Applied domain knowledge to solve business challenges.",
                "Optimized processes and improved overall performance.",
            ]
        normalized_exp.append(
            {"company": company, "title": "", "duration": "", "bullets": bullets}
        )
    while len(normalized_exp) < 3:
        idx = len(normalized_exp)
        normalized_exp.append(
            {
                "company": _PLACEHOLDER_COMPANIES[idx],
                "title": "",
                "duration": "",
                "bullets": [
                    "Designed and implemented category-specific solutions following industry standards.",
                    "Collaborated with cross-functional teams to deliver quality outcomes.",
                    "Applied analytical and problem-solving skills to meet objectives.",
                    "Supported continuous improvement of processes and deliverables.",
                ],
            }
        )
    resume_data["experience"] = normalized_exp

    # Projects
    projects = resume_data.get("projects", [])[:2]
    for proj in projects:
        proj["name"] = _strip_dates(proj.get("name", "Category Project"))
        proj["description"] = _strip_dates(proj.get("description", ""))
        proj["tech"] = _strip_dates(proj.get("tech", ""))
    while len(projects) < 2:
        projects.append(
            {
                "name": "Professional Domain Project",
                "description": (
                    "Developed a generalized solution demonstrating core competencies "
                    "and best practices relevant to the field."
                ),
                "tech": "Category-relevant tools and technologies",
            }
        )
    resume_data["projects"] = projects[:2]

    # Education
    edu_field = ""
    if resume_data.get("education"):
        edu_field = _strip_dates(
            resume_data["education"][0].get("degree", "")
            or resume_data["education"][0].get("institution", "")
        )
    if not edu_field:
        edu_field = "Relevant academic field or related discipline"
    resume_data["education"] = [
        {
            "degree": edu_field,
            "institution": _PLACEHOLDER_UNIVERSITY,
            "year": "",
        }
    ]

    # Certifications
    certs = [_strip_dates(c) for c in resume_data.get("certifications", []) if c]
    if len(certs) < 3:
        certs = list(_GENERIC_CERTS)
    resume_data["certifications"] = certs[:3]

    # Achievements
    achievements = [
        _strip_dates(a) for a in resume_data.get("achievements", []) if a
    ][:4]
    if len(achievements) < 4:
        achievements = [
            "Successfully delivered projects aligned with organizational goals and quality standards.",
            "Demonstrated strong problem-solving and analytical capabilities in complex situations.",
            "Improved processes and workflows through collaboration and effective communication.",
            "Contributed to team success by maintaining high standards of professional excellence.",
        ]
    resume_data["achievements"] = achievements[:4]

    resume_data["summary"] = _strip_dates(resume_data.get("summary", ""))
    return resume_data
