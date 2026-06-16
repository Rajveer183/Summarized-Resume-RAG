"""
Section-aware resume chunker.

Strategy:
  1. Detect standard resume section headers (Summary, Skills, Experience, etc.)
  2. Split text by sections and create one chunk per section
  3. If a section is too large, further split with RecursiveCharacterTextSplitter
  4. Fall back to RecursiveCharacterTextSplitter for unstructured text

Each chunk carries metadata:
  - category: str
  - source_file: str
  - section_name: str
  - chunk_id: str  (unique identifier)
"""
import re
import uuid
from typing import Dict, List

from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

# ── Section header patterns ────────────────────────────────────────────────────
SECTION_PATTERNS = [
    (r"\bprofessional\s+summary\b|\bsummary\b|\bobjective\b|\bprofile\b", "Summary"),
    (r"\btechnical\s+skills\b|\bskills\b|\bcore\s+competencies\b|\bcompetencies\b", "Skills"),
    (r"\bwork\s+experience\b|\bexperience\b|\bemployment\b|\bprofessional\s+experience\b", "Experience"),
    (r"\bprojects?\b|\bkey\s+projects?\b|\bproject\s+highlights?\b", "Projects"),
    (r"\beducation\b|\bacademic\s+background\b|\bqualifications?\b", "Education"),
    (r"\bcertifications?\b|\bcertified\b|\blicenses?\b", "Certifications"),
    (r"\bachievements?\b|\bawards?\b|\bhonors?\b|\baccomplishments?\b", "Achievements"),
    (r"\bpublications?\b", "Publications"),
    (r"\blanguages?\b", "Languages"),
    (r"\bvolunteer\b|\bvolunteer\s+experience\b", "Volunteer"),
    (r"\bhobbies?\b|\binterests?\b|\bactivities\b", "Interests"),
    (r"\breferences?\b", "References"),
]

# Build a single compiled regex for section detection
_SECTION_HEADER_RE = re.compile(
    r"^(" + "|".join(p for p, _ in SECTION_PATTERNS) + r")\s*[:\-]?\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Max chars per chunk before further splitting
MAX_CHUNK_SIZE = 700
CHUNK_OVERLAP = 100


def _label_section(header_text: str) -> str:
    """Map a detected header string to a canonical section label."""
    header_lower = header_text.lower().strip()
    for pattern, label in SECTION_PATTERNS:
        if re.search(pattern, header_lower, re.IGNORECASE):
            return label
    return "General"


def _recursive_split(text: str, chunk_size: int = MAX_CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Fallback splitter: split text into chunks of up to chunk_size characters
    with overlap, respecting paragraph/sentence boundaries where possible.
    """
    separators = ["\n\n", "\n", ". ", " ", ""]
    chunks = []

    def split_by_separator(text: str, sep_idx: int) -> List[str]:
        if len(text) <= chunk_size or sep_idx >= len(separators):
            return [text] if text.strip() else []
        sep = separators[sep_idx]
        parts = text.split(sep) if sep else list(text)
        result = []
        current = ""
        for part in parts:
            candidate = (current + sep + part) if current else part
            if len(candidate) <= chunk_size:
                current = candidate
            else:
                if current:
                    result.append(current)
                # If single part is too long, recurse with next separator
                if len(part) > chunk_size:
                    result.extend(split_by_separator(part, sep_idx + 1))
                    current = ""
                else:
                    current = part
        if current:
            result.append(current)
        return result

    raw_chunks = split_by_separator(text, 0)

    # Add overlap between consecutive chunks
    for i, chunk in enumerate(raw_chunks):
        if i > 0 and overlap > 0:
            prev = raw_chunks[i - 1]
            overlap_text = prev[-overlap:] if len(prev) > overlap else prev
            chunk = overlap_text + "\n" + chunk
        chunks.append(chunk.strip())

    return [c for c in chunks if c]


def chunk_resume(
    text: str,
    category: str,
    source_file: str,
) -> List[Dict]:
    """
    Chunk a single resume text into section-aware chunks.

    Returns a list of dicts:
        {
            "text": str,
            "metadata": {
                "category": str,
                "source_file": str,
                "section_name": str,
                "chunk_id": str,
            }
        }
    """
    chunks: List[Dict] = []

    # ── Find section boundaries ───────────────────────────────────────────────
    matches = list(_SECTION_HEADER_RE.finditer(text))

    if not matches:
        # No recognizable sections — use fallback splitter on full text
        logger.debug(f"No sections found in {source_file}, using fallback splitter")
        sub_chunks = _recursive_split(text)
        for idx, sub in enumerate(sub_chunks):
            chunks.append({
                "text": sub,
                "metadata": {
                    "category": category,
                    "source_file": source_file,
                    "section_name": "General",
                    "chunk_id": str(uuid.uuid4()),
                },
            })
        return chunks

    # ── Extract sections between header matches ───────────────────────────────
    # Add sentinel for text before first header
    boundaries = [(0, "Preamble")] + [
        (m.start(), _label_section(m.group(0))) for m in matches
    ] + [(len(text), None)]

    for i in range(len(boundaries) - 1):
        start_pos, section_name = boundaries[i]
        end_pos = boundaries[i + 1][0]

        # Extract section content (skip the header line itself)
        section_text = text[start_pos:end_pos].strip()

        # Remove the header line from the start of section text
        if i > 0:
            section_text = "\n".join(section_text.split("\n")[1:]).strip()

        if not section_text:
            continue

        # If section is within chunk size, keep as single chunk
        if len(section_text) <= MAX_CHUNK_SIZE:
            chunks.append({
                "text": section_text,
                "metadata": {
                    "category": category,
                    "source_file": source_file,
                    "section_name": section_name,
                    "chunk_id": str(uuid.uuid4()),
                },
            })
        else:
            # Further split large sections
            sub_chunks = _recursive_split(section_text)
            for sub in sub_chunks:
                chunks.append({
                    "text": sub,
                    "metadata": {
                        "category": category,
                        "source_file": source_file,
                        "section_name": section_name,
                        "chunk_id": str(uuid.uuid4()),
                    },
                })

    logger.debug(
        f"Chunked {source_file} → {len(chunks)} chunks "
        f"across {len(set(c['metadata']['section_name'] for c in chunks))} sections"
    )
    return chunks
