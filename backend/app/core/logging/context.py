"""
Request correlation context.

The request ID lives in a contextvar, set once per request by
RequestContextMiddleware (see middleware.py). A custom LogRecord factory
stamps every log record - anywhere in the app, at any layer - with the
current request ID automatically. This is what lets a service, repository,
or provider log a line that is correlated to its request without any of
those layers knowing about requests at all.
"""

import logging
from contextvars import ContextVar, Token

_NO_REQUEST = "-"

_request_id_var: ContextVar[str] = ContextVar("request_id", default=_NO_REQUEST)


def get_request_id() -> str:
    """Current request ID, or "-" if called outside a request (e.g. at startup)."""
    return _request_id_var.get()


def set_request_id(request_id: str) -> Token:
    """Sets the request ID for the current context. Returns a token for reset_request_id()."""
    return _request_id_var.set(request_id)


def reset_request_id(token: Token) -> None:
    """Restores the previous request ID. Always call this in a `finally`."""
    _request_id_var.reset(token)


def _install_request_id_log_factory() -> None:
    """
    Wraps the current LogRecordFactory so every record gets `.request_id`.

    Installing this at record-creation time (rather than via a
    logging.Filter on one specific handler) means `record.request_id` is
    guaranteed to exist for ANY handler that processes the record -
    including pytest's caplog - regardless of handler attachment order.
    """
    current_factory = logging.getLogRecordFactory()

    if getattr(current_factory, "_request_id_aware", False):
        # Already installed (e.g. setup_logging() imported more than once).
        return

    def record_factory(*args, **kwargs) -> logging.LogRecord:
        record = current_factory(*args, **kwargs)
        record.request_id = _request_id_var.get()
        return record

    record_factory._request_id_aware = True
    logging.setLogRecordFactory(record_factory)


# Installed at import time (not gated behind setup_logging()) so that
# record.request_id always exists once this module has been imported once,
# even for a log call that happens to fire before setup_logging() runs.
_install_request_id_log_factory()
