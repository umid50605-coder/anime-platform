# Project Rules

These are working rules for this codebase, not aspirations. If a change
can't follow one of these, that's a signal to stop and reconsider the
change, not to make an exception silently.

## Layering

- **API handlers stay thin.** A router function parses the request, calls
  exactly one service method, and shapes the response. No business logic,
  no direct DB queries, no direct provider calls in `app/api/*/router.py`.
- **Business logic lives in services**, and only there. If you find
  yourself writing an `if` that encodes a business rule anywhere else
  (a router, a repository, a React component), move it to a service.
- **DB access goes through the repository layer.** Services never import
  `sqlalchemy` or touch a `Session` directly - they receive a repository
  instance.
- **External providers are only reached through their interface**
  (`AnimeProvider`, `VideoProvider`) and only constructed via their
  factory function. Never import `MockAnimeProvider` (or a future real
  vendor adapter) anywhere except `app/integrations/*/factory.py`.
- **Wiring lives in `app/api/deps.py` only.** That's the one place that
  turns a DB session into a repository into a service.

## Authentication boundary

- **The core viewing flow never requires an account.** Home, catalog,
  anime detail, episodes, search, and watching an episode (including the
  stream endpoint) must work with zero authentication steps and no
  `Authorization` header. Don't add a `get_current_user`/`useAuth()`-based
  gate to any of these, even indirectly (e.g. by making a page depend on
  data from an endpoint that requires auth).
- **Account-scoped features stay isolated, not deleted.** Favorites, watch
  progress/history, and the profile page are legitimate features that
  need an account to mean anything - keep them working for signed-in
  users without pulling the public flow behind them. Don't reason "X needs
  login, therefore the whole site needs login."
- **No new auth mechanism** (sessions, cookies, a second token scheme,
  etc.) without a real reason - the existing JWT + Argon2id setup is the
  one and only mechanism until something concrete requires otherwise.

## Scope discipline

- **No overengineering.** Don't add a feature, abstraction, or
  configuration knob before something in this codebase actually needs it.
  If you're adding a layer "for later," stop and write it down in
  `docs/decisions/` instead - don't build it speculatively.
- **No Telegram code in this repository's backend/frontend yet.** When
  Telegram integration starts, it must be a separate module that
  subscribes to domain events - it must never be called directly from
  inside `AnimeService`, `WatchService`, etc.
- **No adaptive streaming, bandwidth estimation, or prefetching** until a
  real, measured problem justifies it.
- **No message queue / Redis / Kafka** until there's an actual multi-process
  or multi-service need for one.

## Secrets and configuration

- **No secrets in source control.** All configuration comes from
  environment variables via `app/core/config` (backend) or `import.meta.env`
  (frontend, `VITE_`-prefixed only). `.env` files are gitignored;
  `.env.example` files are not, and must stay free of real credentials.
- **No hardcoded API keys or DB credentials anywhere in the codebase.**
- **`DEBUG` stays `false` by default.** With it `true`, unhandled
  exceptions return a raw traceback to the HTTP client and skip the app's
  own exception handler/logging entirely (see
  `docs/decisions/0003-request-correlation-logging.md`). Only ever set it
  `true` for local troubleshooting, never in a committed default.

## Logging

- **Logging is a cross-cutting concern - it lives at boundaries, not
  scattered through business logic.** Request correlation and
  request-lifecycle logging live in `RequestContextMiddleware` (one place).
  Provider-failure logging lives in the `Logging*Provider` decorators
  (wired in only at the factory functions), never inside `AnimeService`/
  `WatchService`/etc. DB-error logging lives in the single `get_db()`
  dependency, never duplicated across repository methods. Follow this
  pattern for any new cross-cutting logging need instead of adding
  `logger.x(...)` calls inside a service method.
- **Every log line is correlated.** Anything logged during a request
  automatically carries `request_id` (see
  `app/core/logging/context.py`) - don't thread a request id parameter
  through function signatures to achieve this.
- **Never log:** plaintext passwords, password hashes, JWTs, the
  `Authorization` header, cookies, API keys, DB connection strings/
  credentials, or a raw external-provider error message/response body (it
  could carry a vendor's secret). Log identifiers (user id) and exception
  *types*, not exception message strings, when the message could carry
  anything sensitive - see `test_sensitive_data_is_never_logged` and the
  provider/DB logging tests in `tests/backend/test_logging.py` for the
  exact bar new logging code needs to clear.
- **Log levels:** INFO for normal request lifecycle and successful
  security events (login/registration succeeded); WARNING for
  authentication failures and unauthorized-access attempts; ERROR for
  unhandled exceptions, provider failures, and DB errors. Don't make a
  normal successful request log at WARNING/ERROR "just in case."

## Rate limiting

- **Scoped to specific routes via `dependencies=[...]`, never a global
  middleware.** Currently only `/api/auth/register` and `/api/auth/login`
  (5/minute/IP each, independent of each other) - see
  `docs/decisions/0004-auth-rate-limiting.md`. This makes "public
  browsing/search/watch is unaffected" true by construction, not by an
  exclusion list that has to stay correct as routes are added.
- **`RateLimiter` is an interface** (`app/core/rate_limit/limiter.py`), same
  shape as `AnimeProvider`/`VideoProvider`. Only `InMemoryRateLimiter`
  exists today - per-process state only, no Redis/distributed backend yet
  (a known, accepted limitation, not an oversight). Add a new backend by
  implementing the interface and adding a branch in `factory.py`, not by
  changing the dependency or the routes using it.
- **Never trust `X-Forwarded-For` or similar client-supplied headers for
  rate-limit identity** until a real reverse-proxy/trusted-upstream config
  exists - `request.client.host` only, for now. Honoring a spoofable header
  without a trusted proxy in front would let the limit be bypassed
  trivially.
- **Any test touching a rate-limited endpoint relies on
  `tests/backend/conftest.py`'s autouse `_reset_rate_limiter` fixture.**
  Don't reset the limiter manually inside a test - the autouse fixture
  already guarantees a clean state before and after every test, including
  ones that don't otherwise touch auth.

## Testing

- **Meaningful business logic needs a test.** A service method with a
  validation rule, an upsert, or an error path should have a unit test
  (see `tests/backend/test_watch_service.py` for the pattern: fake
  repositories/providers, no DB, no HTTP).
- **Don't call something "done" without running it.** Before considering a
  change complete: run `pytest`, `ruff check`/`ruff format --check`
  (backend), and `npm run build`/`npm run lint` (frontend). Fix what they
  find; don't report success with known-failing checks.

## Multi-agent / multi-contributor discipline

- **Check before you touch another module.** Read `ARCHITECTURE.md` and
  `docs/decisions/` before changing a layer you didn't just build -
  someone (or something) else's design decision might be intentional.
- **Deviations are documented, never silent.** If the actual best path
  differs from an agreed structure or spec, say so explicitly (what
  changed, why, what alternative was considered, what the impact is) -
  see `ARCHITECTURE.md` section 10 for the standing example.
- **Record architecture decisions** as they're made, in
  `docs/decisions/NNNN-title.md` (see `docs/decisions/0001-initial-stack.md`
  for the format).

## Known, accepted warnings

These are recorded here deliberately rather than silently ignored:

- **7 `react(set-state-in-effect)` oxlint warnings** in the data-fetching
  hooks/effects (`useWatchProgress`, `useWatchHistory`, `useFavorites`,
  `useSearch`, `AnimeDetailPage`, `AuthContext`, `WatchPage`). This is the standard
  "set loading, fetch, set result" pattern predating React Suspense-based
  data fetching. Restructuring around it would mean adopting a data-
  fetching library (React Query, SWR, or Suspense-based fetching) - that's
  a real option for later, but it's not justified yet for a handful of
  simple GET requests, and doing it now would be exactly the kind of
  speculative abstraction this document tells you not to add. Revisit if
  the frontend's data-fetching needs grow (caching, refetching,
  invalidation across pages).
- **A handful of upstream `DeprecationWarning`s in the pytest run**
  (from `starlette`'s `TestClient`/`httpx` pairing, an `anyio` internal
  alias, and passlib's own use of the deprecated stdlib `crypt` module and
  an internal `argon2-cffi` version check). These originate inside
  third-party packages, not this codebase, and don't affect behavior.
