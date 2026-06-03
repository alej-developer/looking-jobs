"""
logger.py — Structured logging setup using the Rich library.

Provides a consistent, colored log format across the entire application.
"""

import logging
import sys

from rich.logging import RichHandler


def get_logger(name: str, level: str | None = None) -> logging.Logger:
    """Create and return a configured logger.

    Args:
        name: Logger name (usually ``__name__`` from the calling module).
        level: Override log level. If None, reads from the ``LOG_LEVEL``
               environment variable (default: ``INFO``).

    Returns:
        A ``logging.Logger`` with a Rich console handler attached.
    """
    if level is None:
        import os

        level = os.getenv("LOG_LEVEL", "INFO")

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers on repeated calls
    if not logger.handlers:
        handler = RichHandler(
            show_time=True,
            show_path=True,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            log_time_format="[%Y-%m-%d %H:%M:%S]",
        )
        handler.setLevel(level)
        fmt = logging.Formatter("%(message)s", datefmt="[%X]")
        handler.setFormatter(fmt)
        logger.addHandler(handler)

    return logger
