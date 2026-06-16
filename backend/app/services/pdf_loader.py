"""
PDF text extraction service.
Primary extractor: pdfplumber
Fallback extractor: PyMuPDF (fitz)
"""
from pathlib import Path
from typing import Optional

from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def extract_text_pdfplumber(pdf_path: Path) -> Optional[str]:
    """Extract text from a PDF using pdfplumber."""
    try:
        import pdfplumber

        with pdfplumber.open(str(pdf_path)) as pdf:
            pages_text = []
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)
            full_text = "\n".join(pages_text).strip()
            if full_text:
                return full_text
    except Exception as e:
        logger.warning(f"pdfplumber failed for {pdf_path.name}: {e}")
    return None


def extract_text_pymupdf(pdf_path: Path) -> Optional[str]:
    """Extract text from a PDF using PyMuPDF (fitz) as fallback."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(pdf_path))
        pages_text = []
        for page in doc:
            text = page.get_text("text")
            if text:
                pages_text.append(text)
        doc.close()
        full_text = "\n".join(pages_text).strip()
        if full_text:
            return full_text
    except Exception as e:
        logger.warning(f"PyMuPDF failed for {pdf_path.name}: {e}")
    return None


def load_pdf(pdf_path: Path, *, fast: bool = False) -> Optional[str]:
    """
    Load and extract text from a PDF file.
    Tries pdfplumber first, falls back to PyMuPDF (unless fast=True).
    Returns None if both fail.
    """
    from backend.app.config import config

    use_fast = fast or config.INGEST_FAST_PDF

    if use_fast:
        text = extract_text_pymupdf(pdf_path)
        if text:
            logger.debug(f"Extracted {len(text)} chars from {pdf_path.name} (PyMuPDF)")
            return text
        text = extract_text_pdfplumber(pdf_path)
        if text:
            logger.debug(f"Extracted {len(text)} chars from {pdf_path.name} (pdfplumber)")
            return text
    else:
        text = extract_text_pdfplumber(pdf_path)
        if text:
            logger.debug(f"Extracted {len(text)} chars from {pdf_path.name} (pdfplumber)")
            return text

        logger.info(f"Retrying with PyMuPDF: {pdf_path.name}")
        text = extract_text_pymupdf(pdf_path)
    if text:
        logger.debug(f"Extracted {len(text)} chars from {pdf_path.name} (PyMuPDF)")
        return text

    logger.error(f"Could not extract text from {pdf_path.name}")
    return None
