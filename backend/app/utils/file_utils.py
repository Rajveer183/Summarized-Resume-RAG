"""File system helpers for the Resume RAG pipeline."""
from pathlib import Path
from typing import List

from backend.app.utils.logger import get_logger

logger = get_logger(__name__)


def list_categories(data_path: Path) -> List[str]:
    """
    Return sorted list of category folder names inside data_path.
    Only returns actual directories.
    """
    if not data_path.exists():
        logger.error(f"Data path does not exist: {data_path}")
        return []

    categories = sorted(
        [d.name for d in data_path.iterdir() if d.is_dir()]
    )
    logger.info(f"Found {len(categories)} categories in {data_path}")
    return categories


def list_pdfs(category_path: Path) -> List[Path]:
    """
    Return list of all PDF file paths inside a category directory.
    """
    if not category_path.exists():
        logger.warning(f"Category path does not exist: {category_path}")
        return []

    pdfs = sorted(category_path.glob("*.pdf"))
    logger.debug(f"Found {len(pdfs)} PDFs in {category_path.name}")
    return pdfs


def get_category_path(data_path: Path, category: str) -> Path:
    """Return the full path for a given category name."""
    return data_path / category
