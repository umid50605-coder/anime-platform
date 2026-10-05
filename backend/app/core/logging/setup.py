"""
Basic logging configuration.

Deliberately simple: one console handler, one format, level from settings.
No log aggregation / shipping is wired up yet - that belongs to
infrastructure decisions that have not been made (see ARCHITECTURE.md).

Every record includes request_id (see context.py) so log lines from any
layer - API, service, repository, provider - can be correlated to the HTTP
request that caused them, without threading a request_id parameter through
every function call.
"""

import logging
import sys

# Importing this (not "from app.core.logging import context") avoids any
# ambiguity with app/core/logging/__init__.py, which is still mid-import
# when this module first runs. The import's only purpose here is its
# side effect: installing the request-id-aware LogRecord factory.
import app.core.logging.context  # noqa: E402,F401
from app.core.config import get_settings

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | request_id=%(request_id)s | %(message)s"


def setup_logging() -> None:
    settings = get_settings()
    root = logging.getLogger()

    if root.handlers:
        # Avoid duplicate handlers if setup_logging() is called more than
        # once (e.g. during tests that create the app multiple times).
        return

    root.setLevel(settings.log_level)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
