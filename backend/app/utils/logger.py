"""Structured logger for the Resume RAG backend."""
import logging
import sys
from pathlib import Path


def get_logger(name: str) -> logging.Logger:
    """
    Returns a configured logger that writes to stdout with timestamps.
    Usage:
        from backend.app.utils.logger import get_logger
        logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        # Avoid adding duplicate handlers on re-import
        return logger

    logger.setLevel(logging.DEBUG)

    # ── Console handler ───────────────────────────────────────────────────────
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger
