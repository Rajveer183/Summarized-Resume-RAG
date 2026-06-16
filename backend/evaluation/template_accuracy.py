"""
Template accuracy — validates universal resume template structure and section order.
"""
import re
from typing import List, Tuple

from backend.app.utils.category_titles import get_professional_title
from backend.evaluation._utils import clamp_percent

# (label, checker) — order matters for template sequence score
REQUIRED_TEMPLATE_CHECKS: List[Tuple[str, str]] = [
    ("section_candidate_title", "CANDIDATE TITLE"),
    ("section_summary", "PROFESSIONAL SUMMARY"),
    ("section_skills", "TECHNICAL SKILLS"),
    ("section_experience", "WORK EXPERIENCE"),
    ("section_projects", "PROJECTS"),
    ("section_education", "EDUCATION"),
    ("section_certifications", "CERTIFICATIONS"),
    ("section_achievements", "ACHIEVEMENTS"),
    ("company_xyz", "XYZ Company"),
    ("company_abc", "ABC Company"),
    ("company_def", "DEF Company"),
    ("university_xyz", "XYZ University"),
]


def _section_positions(text_upper: str) -> List[int]:
    markers = [
        "PROFESSIONAL SUMMARY",
        "TECHNICAL SKILLS",
        "WORK EXPERIENCE",
        "PROJECTS",
        "EDUCATION",
        "CERTIFICATIONS",
        "ACHIEVEMENTS",
    ]
    positions = []
    for marker in markers:
        pos = text_upper.find(marker)
        if pos >= 0:
            positions.append(pos)
    return positions


def compute_template_accuracy(resume_text: str, category: str) -> float:
    """
    Template Accuracy = correct_elements / required_elements × 100
    """
    if not resume_text.strip():
        return 0.0

    upper = resume_text.upper()
    correct = 0
    total = len(REQUIRED_TEMPLATE_CHECKS)

    for _key, needle in REQUIRED_TEMPLATE_CHECKS:
        if needle.upper() in upper:
            correct += 1

    # Title should match category professional title
    expected_title = get_professional_title(category).upper()
    if expected_title in upper:
        correct += 1
    total += 1

    # Section order: each subsequent section appears later in the document
    positions = _section_positions(upper)
    if len(positions) >= 2 and positions == sorted(positions):
        correct += 1
    total += 1

    return clamp_percent((correct / total) * 100.0)
