"""
Grounding accuracy — share of generated facts supported by retrieved context.
"""
import re
from typing import Any, Dict, List, Set

from backend.evaluation.content_accuracy import build_context_corpus, embed_texts_bge, cosine_similarity_percent

_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into", "using",
    "have", "has", "was", "were", "are", "been", "being", "their", "they",
    "will", "would", "should", "could", "about", "through", "during", "while",
    "professional", "candidate", "company", "university", "project",
}


def _extract_section(text: str, marker: str) -> str:
    pattern = rf"===\s*{re.escape(marker)}\s*===\s*\n(.*?)(?=\n===\s*\w|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def _lines_as_facts(section_text: str) -> List[str]:
    facts: List[str] = []
    for line in section_text.split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith(("•", "-", "*", "–")):
            line = line.lstrip("•-*– ").strip()
        if line.upper().startswith(
            ("XYZ COMPANY", "ABC COMPANY", "DEF COMPANY", "XYZ UNIVERSITY")
        ):
            continue
        if line.lower().startswith("technologies/skills used:"):
            tech = line.split(":", 1)[-1].strip()
            facts.extend(_split_terms(tech))
            continue
        if len(line) >= 4 and not line.startswith("==="):
            facts.append(line)
            if ":" in line and len(line.split(":", 1)[0]) < 40:
                facts.extend(_split_terms(line.split(":", 1)[-1]))
    return facts


def _split_terms(text: str) -> List[str]:
    parts = re.split(r"[,;|/•\n]", text)
    return [p.strip() for p in parts if len(p.strip()) >= 3]


def extract_generated_facts(resume_text: str) -> List[str]:
    """Extract skills, tools, responsibilities, projects, certifications from resume."""
    sections = [
        "TECHNICAL SKILLS",
        "WORK EXPERIENCE",
        "PROJECTS",
        "CERTIFICATIONS",
        "ACHIEVEMENTS",
        "PROFESSIONAL SUMMARY",
    ]
    facts: List[str] = []
    for section in sections:
        facts.extend(_lines_as_facts(_extract_section(resume_text, section)))

    # Dedupe while preserving order
    seen: Set[str] = set()
    unique: List[str] = []
    for fact in facts:
        key = fact.lower()
        if key in seen or len(key) < 4:
            continue
        seen.add(key)
        unique.append(fact)
    return unique[:80]


def _keyword_supported(fact: str, context_lower: str) -> bool:
    fact_lower = fact.lower()
    if fact_lower in context_lower:
        return True
    tokens = [t for t in re.findall(r"[a-zA-Z0-9+#.]+", fact_lower) if len(t) >= 3]
    tokens = [t for t in tokens if t not in _STOPWORDS]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in context_lower)
    return hits / len(tokens) >= 0.6


def _embedding_supported(fact: str, context_emb: List[float]) -> bool:
    try:
        fact_emb = embed_texts_bge([fact])[0]
        return cosine_similarity_percent(fact_emb, context_emb) >= 72.0
    except Exception:
        return False


def compute_grounding_accuracy(
    resume_text: str,
    context_chunks: List[Dict[str, Any]],
) -> float:
    """
    Grounding Accuracy = supported_facts / total_facts × 100
    """
    context = build_context_corpus(context_chunks)
    facts = extract_generated_facts(resume_text)
    if not facts:
        return 100.0

    context_lower = context.lower()
    context_emb = embed_texts_bge([context])[0] if context.strip() else []

    supported = 0
    for fact in facts:
        if _keyword_supported(fact, context_lower):
            supported += 1
        elif context_emb and _embedding_supported(fact, context_emb):
            supported += 1

    return (supported / len(facts)) * 100.0
