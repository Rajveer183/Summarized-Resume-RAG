"""
Resume Generator Service — orchestrates the full RAG pipeline:
  1. Retrieve relevant chunks from ChromaDB
  2. Rerank chunks
  3. Build prompt
  4. Call NVIDIA NIM LLM
  5. Return generated resume text
"""
from typing import Dict, Any

from openai import OpenAI

from backend.app.config import config
from backend.app.prompts.resume_prompt import build_prompt
from backend.app.services.resume_sanitizer import sanitize_resume_text
from backend.app.services.retriever import retrieve_chunks
from backend.app.services.reranker import rerank
from backend.app.utils.category_titles import get_professional_title
from backend.app.utils.logger import get_logger

logger = get_logger(__name__)

# NVIDIA NIM client (OpenAI-compatible API)
_nvidia_client = None


def _get_nvidia_client() -> OpenAI:
    """Lazy-initialize the NVIDIA NIM OpenAI-compatible client."""
    global _nvidia_client
    if _nvidia_client is None:
        if not config.NVIDIA_API_KEY:
            raise ValueError(
                "NVIDIA_API_KEY is not set. Please add it to your .env file. "
                "Get your key at: https://build.nvidia.com/"
            )
        _nvidia_client = OpenAI(
            base_url=config.NVIDIA_BASE_URL,
            api_key=config.NVIDIA_API_KEY,
        )
        logger.info(f"NVIDIA NIM client initialized (model: {config.NVIDIA_MODEL})")
    return _nvidia_client


def generate_resume(category: str) -> Dict[str, Any]:
    """
    Full RAG pipeline: retrieve → rerank → generate resume.

    Args:
        category: Resume category name (e.g., "INFORMATION-TECHNOLOGY")

    Returns:
        Dict with:
            - resume_text: str  (structured resume text from LLM)
            - chunks_used: int  (number of context chunks used)
            - sections_covered: list[str]  (sections found in context)
    """
    logger.info(
        f"Starting resume generation for category: {category} "
        f"({get_professional_title(category)})"
    )

    # ── Step 1: Retrieve relevant chunks ──────────────────────────────────────
    chunks = retrieve_chunks(category)

    if not chunks:
        raise ValueError(
            f"No data found for category '{category}'. "
            "Please run ingestion first: python backend/ingest.py"
        )

    # ── Step 2: Rerank chunks ─────────────────────────────────────────────────
    query = f"professional {category.replace('-', ' ').lower()} resume"
    reranked_chunks = rerank(query=query, chunks=chunks)

    sections_covered = list(set(
        c["metadata"].get("section_name", "General") for c in reranked_chunks
    ))
    logger.info(
        f"Using {len(reranked_chunks)} chunks covering sections: {sections_covered}"
    )

    # ── Step 3: Build prompt ──────────────────────────────────────────────────
    system_prompt, user_prompt = build_prompt(
        category=category,
        context_chunks=reranked_chunks,
    )

    # ── Step 4: Call NVIDIA NIM LLM ───────────────────────────────────────────
    client = _get_nvidia_client()

    logger.info(f"Calling NVIDIA NIM model: {config.NVIDIA_MODEL}")
    response = client.chat.completions.create(
        model=config.NVIDIA_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=config.LLM_TEMPERATURE,
        top_p=config.LLM_TOP_P,
        max_tokens=config.LLM_MAX_TOKENS,
    )

    resume_text = response.choices[0].message.content.strip()
    resume_text = sanitize_resume_text(resume_text, category)
    logger.info(
        f"Resume generated: {len(resume_text)} characters, "
        f"model: {config.NVIDIA_MODEL}"
    )

    return {
        "resume_text": resume_text,
        "chunks_used": len(reranked_chunks),
        "sections_covered": sections_covered,
        "model_used": config.NVIDIA_MODEL,
    }
