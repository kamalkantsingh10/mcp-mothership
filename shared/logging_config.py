"""Logging setup for MCP Mothership.

All log output goes to stderr and a rotating log file.
stdout is reserved for MCP stdio protocol.
"""

import logging
import os
import sys
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")


def setup_logging(
    log_level: str = "INFO",
    log_name: str = "server",
    max_bytes: int = 5_242_880,
    backup_count: int = 3,
) -> None:
    """Configure Python stdlib logging to output to stderr and a log file.

    Args:
        log_level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_name: Name used for the log file (e.g., "imagen" → logs/imagen.log).
        max_bytes: Maximum log file size before rotation (default 5MB).
        backup_count: Number of rotated backup files to keep (default 3).
    """
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO

    root_logger = logging.getLogger()
    root_logger.setLevel(numeric_level)

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s"
    )

    # stderr handler
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(numeric_level)
    stderr_handler.setFormatter(formatter)
    root_logger.addHandler(stderr_handler)

    # File handler — rotating, 5MB max, 3 backups
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"{log_name}.log")
    file_handler = RotatingFileHandler(
        log_file, maxBytes=max_bytes, backupCount=backup_count
    )
    file_handler.setLevel(numeric_level)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)
