from __future__ import annotations
import logging
from rich.logging import RichHandler


_logger = None


def get_logger(name: str = "ai_adapter"):
    global _logger
    if _logger:
        return _logger
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        datefmt="[%X]",
        handlers=[RichHandler(rich_tracebacks=True)]
    )
    _logger = logging.getLogger(name)
    return _logger