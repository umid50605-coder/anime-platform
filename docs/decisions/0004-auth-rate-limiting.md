# 0004 - Auth rate limiting

Status: Accepted
Date: 2026-09-30

## Context

`/api/auth/register` and `/api/auth/login` had no protection against
brute-force/credential-stuffing or registration-spam abuse. The brief
required a fix scoped strictly to these two endpoints - public
catalog/search/watch and already-authenticated endpoints must be provably
unaffected - using no new dependency and no Redis/distributed storage for
this pass.

## Decision

**Hand-rolled, in-memory, sliding-window-log limiter**, applied only via
`dependencies=[Depends(rate_limited(...))]` on the two auth routes - never
a global middleware. 5 requests/minute/IP on each of register and login,
independently (namespaced by an `action` label, so exhausting one never
touches the other).

`request.client.host` is the client identifier - no `X-Forwarded-For` or
other proxy header is read. This app has no trusted-proxy/reverse-proxy
configuration; honoring a client-supplied header without one would let the
limit be trivially bypassed by sending a fake `X-Forwarded-For`. Revisit
only once a real deployment topology (and which upstream to trust) is
decided.

### Structure (mirrors `app/integrations/*` on purpose)

```
app/core/rate_limit/
├── limiter.py      RateLimiter (interface) + InMemoryRateLimiter (impl)
├── factory.py      get_rate_limiter() (cached singleton) + reset_rate_limiter()
├── dependency.py   rate_limited(action, max_requests, window_seconds) -> FastAPI dependency
└── __init__.py
```

Same shape as `AnimeProvider`/`VideoProvider`: an interface, one concrete
implementation, a factory. A future distributed backend (Redis-backed, for
multi-process/multi-replica deployments) is a new class implementing
`RateLimiter` plus a branch in `factory.py` - not a rewrite of the
dependency or the routes using it. This is what "keep the limiter isolated
so its backend can be replaced later" means concretely.

### Algorithm

A sliding-window log: a `deque` of monotonic timestamps per key. Each check
prunes timestamps older than the window, then allows the request only if
fewer than `max_requests` remain, appending the new timestamp if so.
`retry_after` is computed from the *oldest* timestamp still in the window
(`ceil(oldest + window - now)`), so it's exact, not a flat guess. Chosen
over a fixed-window counter because a fixed window allows a burst of up to
`2 * max_requests` at the boundary between two windows; a sliding log
doesn't have that edge case and is barely more code.

### Thread safety

Guarded by a single `threading.Lock`. FastAPI runs sync path operation
functions (both `register` and `login` are `def`, not `async def`) in a
worker threadpool, so concurrent requests genuinely execute on different
threads, not just interleaved on one - a lock is necessary for
read-prune-compare-append to be atomic, not optional hardening.

## Known limitation (accepted for this pass)

**State is per-process.** Running multiple `uvicorn` workers or replicas
gives each its own independent counters, so the *effective* limit
multiplies by the process count - a determined attacker distributing
requests across workers could exceed 5/minute in aggregate. This was an
explicit, accepted tradeoff (no Redis/distributed storage this pass), not
an oversight; `RateLimiter` exists specifically so fixing this later is a
new implementation, not a redesign.

## Testing

`tests/backend/test_rate_limit.py` (9 tests): 4 algorithm-level (direct
against `InMemoryRateLimiter` - below-limit success, over-limit rejection
with a valid `retry_after`, independent keys, `reset()`), 5 endpoint-level
(real HTTP - register's own limit + `Retry-After` header, login's limit
independent of register, register's limit independent of login, two
different simulated client IPs (`TestClient(app, client=(ip, port))`) have
independent limits, and public catalog/search/watch endpoints make 20+
calls in one test with zero rate-limit interference).

**Test isolation**: added an `autouse=True` fixture in `conftest.py`
(`_reset_rate_limiter`) that clears the limiter before and after every
test. This isn't just hygiene - Starlette's `TestClient` reports
`request.client.host` as the fixed string `"testclient"` by default
(confirmed empirically), and every test shares the same module-level `app`
object, so without a reset, rate-limit state would silently accumulate
*across unrelated tests* in the same run.

## Alternatives considered

- **SlowAPI** (MIT license, no commercial-use restriction). Rejected for
  this pass per the approved decision to add no new dependency; its
  default in-memory backend has the exact same per-process limitation
  described above, so it wouldn't have avoided that tradeoff either -
  only the amount of code we own would differ.
- **Global middleware** applied to all routes, with an internal allowlist
  of paths to skip. Rejected: scoping via `dependencies=[...]` on exactly
  the two routes that need it makes "public endpoints are unaffected" true
  by construction (the limiter is never even evaluated for other paths),
  rather than true because an exclusion list happens to be correct and
  stays correct as routes are added later.
- **Per-email limiting** (in addition to per-IP). Explicitly out of scope
  per the brief ("Do NOT add per-email limits yet") - would help against a
  distributed attack targeting one specific account, but wasn't asked for
  here.
