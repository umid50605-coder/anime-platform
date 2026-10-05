"""
RequestContextMiddleware: request correlation + request-lifecycle logging.

Registered as the outermost middleware (added last in app/main.py - Starlette
applies middleware in reverse registration order) so that:
- every log line emitted anywhere during the request - including inside
  FastAPI's own exception handling - is tagged with the request ID.
- a request ID exists even for requests that never reach a route (e.g. a
  CORS-rejected request).

This is the ONLY place that decides/logs request-level facts (method, path,
status, duration). It never inspects request/response bodies, so it cannot
leak request payloads (credentials included) into logs.
"""

import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.context import set_request_id
from app.core.logging.setup import get_logger

REQUEST_ID_HEADER = "X-Request-ID"
_MAX_REQUEST_ID_LENGTH = 128
# ASCII letters/digits and -_. only. Deliberately NOT str.isalnum(): that is
# Unicode-aware and would accept e.g. 'é', Cyrillic, or other scripts -
# a client-supplied ID with those would still be safe to put in a header/log
# line, but "ASCII-only" is the explicit, auditable bar this project wants
# for a value that gets echoed back verbatim (see PROJECT_RULES.md).
_SAFE_REQUEST_ID_CHARS = re.compile(r"^[A-Za-z0-9._-]+$")

logger = get_logger(__name__)


def _is_safe_request_id(value: str) -> bool:
    """
    A client-supplied request ID is only reused if it's safe to place
    verbatim into a response header and a log line - bounded length and a
    conservative, ASCII-only charset (blocks non-ASCII scripts as well as
    newlines/control characters that could be used for header or log
    injection).
    """
    if not value or len(value) > _MAX_REQUEST_ID_LENGTH:
        return False
    return bool(_SAFE_REQUEST_ID_CHARS.fullmatch(value))


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        incoming = request.headers.get(REQUEST_ID_HEADER)
        request_id = incoming if incoming and _is_safe_request_id(incoming) else str(uuid.uuid4())

        # NOTE: deliberately no reset_request_id()/finally here. A truly
        # unhandled exception is handled by Starlette's ServerErrorMiddleware,
        # which sits OUTSIDE this middleware (see app/main.py) and calls our
        # app.main.unhandled_exception_handler while this exception is still
        # unwinding through THIS SAME call stack - not a new task. Resetting
        # the contextvar here (even in a `finally`) would clear request_id
        # before that outer handler runs, so its log line and the response's
        # X-Request-ID header would fall back to "no request". Each real
        # request already runs in its own asyncio Task (created by the ASGI
        # server), which gets its own contextvar copy - so never resetting
        # cannot leak a request_id into a *different* request either way.
        set_request_id(request_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.perf_counter() - start) * 1000
            # status=500 is hardcoded, not read off a response object: an
            # exception reaching this branch means call_next() never
            # produced one - any exception that gets here is, by
            # definition, the unhandled case that always maps to a 500.
            logger.error(
                "request errored method=%s path=%s status=500 duration_ms=%.1f",
                request.method,
                request.url.path,
                duration_ms,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        level = logging.INFO if response.status_code < 500 else logging.ERROR
        logger.log(
            level,
            "request method=%s path=%s status=%s duration_ms=%.1f",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        return response
