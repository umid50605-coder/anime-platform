# 0003 - Request correlation and structured logging

Status: Accepted
Date: 2026-09-21

## Context

The foundation had console/startup logging and a global exception handler,
but no request ID/correlation, no structured request-lifecycle logging, no
security-event logging, and no provider/DB failure logging. The brief asked
for a minimal, standard-library-only, production-oriented implementation
that doesn't touch rate limiting, refresh tokens, password reset, email
verification, provider architecture, the DB schema, or public API contracts.

**Audit note:** most of this task's scope (request ID middleware, the
contextvar-based log-record correlation, request-lifecycle logging, the
global exception handler's logging, and auth security-event logging) was
already implemented and tested (`tests/backend/test_logging.py`) when this
pass started. This ADR covers what that implementation got right, the real
bugs found while validating it, and the one genuinely missing piece
(DB error logging) that this pass added.

## Decision

### Request ID (`app/core/logging/context.py`, `middleware.py`)

A `contextvars.ContextVar` holds the current request's ID. A custom
`logging.LogRecordFactory` stamps every `LogRecord` with `.request_id` from
that contextvar automatically - so any layer (service, repository,
provider) can log a line that's correlated to its request without a
`request_id` parameter being threaded through every function call. This
keeps logging a cross-cutting concern instead of polluting business logic.

`RequestContextMiddleware` (a `BaseHTTPMiddleware`, added last in
`app/main.py` so it's outermost among user middleware) reuses a
client-supplied `X-Request-ID` if it's safe (bounded length, conservative
charset - blocks header/log injection via `\r\n` etc.), otherwise generates
a UUID4. It logs one line per request (`method`, `path`, `status`,
`duration_ms`) at INFO (or ERROR for a 5xx), and sets `X-Request-ID` on the
response.

### Provider failure logging (`app/integrations/*/logging_provider.py`)

`LoggingAnimeProvider`/`LoggingVideoProvider` are transparent decorators
implementing the same `AnimeProvider`/`VideoProvider` interface as the
mock providers, wired in only at the factory (`get_anime_provider`/
`get_video_provider`). They log a failure (provider name, operation,
non-secret identifiers like `external_id`) and re-raise unchanged - the
interface, the mock implementations, and `AnimeService`/`WatchService` are
completely untouched. This is the same "wrap, don't modify" approach a real
vendor adapter should get too.

### DB error logging (`app/core/database/session.py`) - added this pass

The one gap found: no DB-specific error logging existed anywhere. Added a
single `try/except SQLAlchemyError` around `yield db` in `get_db()` - the
one function that creates every request-scoped session. Any SQLAlchemy
error raised by a repository using that session is thrown back into this
generator at the `yield` point (the same mechanism `@contextlib.
contextmanager` uses), logged as `exception_type=...` only, and re-raised
unchanged. This was chosen over adding `try/except` to every repository
method: one centralized point, matching the brief's own preference for
"middleware/dependency... markazlashtirilgan yechim," and zero duplicated
logging code across five repository classes.

## Bugs found during validation (pre-existing, not introduced this pass)

Three real issues surfaced while getting the already-written
`test_exception_log_contains_request_id` to actually pass:

1. **`Settings.debug` defaulted to `True`.** With `debug=True`, Starlette's
   `ServerErrorMiddleware` returns its own HTML/text traceback response
   (source lines, file paths) for any unhandled exception and **skips
   calling our registered `@app.exception_handler(Exception)` entirely** -
   meaning the app's own safe `{"detail": "Internal server error"}`
   response and its exception-logging line were both silently dead code in
   the default configuration. Changed the default to `False`
   (`backend/app/core/config/settings.py`, `.env.example`) - a deliberate,
   security-relevant fix squarely inside "production-oriented logging,"
   not scope creep. Opt into debug mode explicitly per environment.

2. **`X-Request-ID` was missing on the one response Starlette's
   `ServerErrorMiddleware` produces.** That middleware sits *outside*
   `RequestContextMiddleware` (Starlette's own middleware always wraps all
   user middleware), so the normal "attach the header after `call_next`
   returns" path in `middleware.py` never runs for a truly unhandled
   exception - that response is built and sent by `ServerErrorMiddleware`
   calling `app.main.unhandled_exception_handler` directly. Fixed by
   setting `X-Request-ID` explicitly in that handler, via
   `get_request_id()`.

3. **The request ID contextvar was reset before that same outer handler
   ran.** `RequestContextMiddleware` used to reset the contextvar in a
   blanket `finally`, which runs even while an exception is *unwinding
   through* `dispatch()` on its way to `ServerErrorMiddleware` - so by the
   time the exception handler executed, `get_request_id()` already read
   the reset-to-default value (`"-"`), not the real request's ID (this is
   what caused bug #2's fix to still fail against the real ID until this
   was found too). Fixed by removing the reset entirely: each real request
   already runs in its own asyncio Task (created by the ASGI server), which
   gets its own contextvar copy, so nothing resets and nothing leaks
   between *different* requests either way - confirmed with a dedicated
   test (`test_sequential_requests_do_not_leak_request_ids`).

None of these three were caused by anything in this pass beyond running
the test that was already written for exactly this scenario to completion
instead of accepting its failure - which is what the brief's regression
instructions asked for ("root cause'ni aniqlab, minimal fix qil").

## Testing

`tests/backend/test_logging.py` (13 tests): request ID generation/reuse/
rejection, response header presence, request-lifecycle log content,
exception log content + header (now passing, via `raise_server_exceptions=
False` - the standard Starlette pattern for testing custom 500 handling,
since its `TestClient` re-raises server exceptions into the test process
by default even when the app handled them correctly), sequential-request
non-leakage, sensitive-data-never-logged (password/token/`Bearer `),
login-failure and unauthorized-access warnings, DB-error logging +
redaction (2 tests, unit-level against `get_db` directly), provider-failure
logging + redaction for both providers (2 tests, unit-level against fakes).

## What is deliberately NOT covered

- No log aggregation/shipping (stdout only) - infrastructure decision, not
  made yet.
- No rate limiting, refresh tokens, password reset, or email verification -
  out of scope per the brief.
- No changes to the provider *interfaces*, the mock implementations, the DB
  schema, or any public API response contract.
