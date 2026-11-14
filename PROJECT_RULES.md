# Project Rules

These rules are mandatory working constraints for the Anime Platform repository. If a change cannot follow a rule, stop and explain the conflict instead of silently making an exception.

## 1. Layering

- **API handlers stay thin.** A router parses the request, calls the relevant service method, and shapes the response. No business logic, direct database queries, or direct provider calls in router modules.
- **Business logic lives in services.** Do not place business rules in routers, repositories, or React components.
- **Database access goes through repositories.** Services must not import SQLAlchemy or manipulate a `Session` directly; they receive repository dependencies.
- **External providers are accessed through interfaces.** Use `AnimeProvider`, `VideoProvider`, and other established interfaces. Concrete implementations are constructed through their factory functions.
- **Dependency wiring lives in `app/api/deps.py`.** Do not construct repositories/services ad hoc inside route handlers.

## 2. Authentication boundary

- **The core browsing/watching flow remains public.** Home, catalog, anime detail, episodes, search, watch, and stream endpoints must work without authentication.
- **Account-scoped features remain isolated.** Favorites, watch progress/history, and profile operations require an account, but must not force authentication on public browsing or watching.
- Do not introduce another authentication mechanism (sessions, a second token scheme, etc.) without an approved technical reason. The current mechanism is JWT with Argon2id password hashing.

## 3. Password reset invariants

- Redeeming a reset token is one transaction. Spending the token, changing the password, expiring other reset links, and revoking the user's refresh sessions must commit or roll back together through the repository transaction boundary.
- Never log a raw reset token, reset URL, password, or email body. Log safe identifiers and exception types only.
- The forgot-password response must not reveal whether an email is registered, inactive, or otherwise eligible.
- Reset tokens are carried in the URL fragment (`#token=`), not a query string. The frontend keeps the token in component state, not persistent web storage.
- Email delivery uses the `EmailSender` interface. The in-memory implementation is not real email delivery. Do not claim that users receive real messages until a production sender is implemented and configured.

## 4. Future roadmap tasks — do not remove or silently absorb

These task entries are part of the project's persistent planning information. Preserve their names and status when editing project documentation.

| Task | Name | Status | Rule |
|---|---|---|---|
| Task 11 | Email Verification | PENDING | Separate task. Do not treat the `EmailSender` interface or password-reset flow as completed email verification. |
| Task 14 | Admin / Content Management | NOT IMPLEMENTED | Separate task. Do not imply an admin panel exists. |
| Task 15 | Deployment, Portability and Production Readiness | PENDING | Separate task. Do not imply the project is production-ready or that deployment choices are finalized. |

Do not start these tasks while working on another task unless the user explicitly authorizes it. When one of these tasks is authorized, audit the current repository and approved task scope first.

## 5. Scope discipline

- Do not overengineer. Add abstractions, dependencies, configuration, or features only when the current requirement justifies them.
- Do not implement Telegram integration as an incidental feature. If approved later, keep it isolated from core anime/watch services and follow a documented architecture decision.
- Do not add adaptive streaming, bandwidth estimation, buffer control, or prefetching without a measured requirement and approved scope.
- Do not add Redis, Kafka, or a message queue without a concrete multi-process or multi-service requirement.
- Do not make unrelated refactors while implementing a task.
- Preserve existing API contracts unless a change is explicitly required and approved.

## 6. Secrets and configuration

- Never commit secrets. Backend configuration comes from environment variables through the established configuration layer; frontend variables must use the `VITE_` prefix.
- `.env` files are ignored by Git. Example environment files must contain placeholders, never real credentials.
- Do not hardcode API keys, database credentials, or private tokens.
- `DEBUG` remains `false` by default. Enable it only for local troubleshooting, never as a committed default.
- The current database strategy is **MySQL primary / SQLite alternative for local development and isolated tests**. Do not silently revert documentation to the superseded SQLite-dev / PostgreSQL-ready strategy.

## 7. Logging and sensitive data

- Keep cross-cutting logging at application boundaries rather than scattering it through business logic.
- Request correlation is handled by the request-context middleware and logging context. Do not pass request IDs through service signatures without a specific need.
- Never log plaintext passwords, password hashes, JWTs, authorization headers, cookies, API keys, database connection strings/credentials, raw reset tokens, reset URLs, email bodies, or unfiltered provider response/error bodies.
- Prefer safe identifiers and exception types when logging failures.
- Use appropriate log levels: INFO for normal request lifecycle and successful security events; WARNING for authentication failures and unauthorized attempts; ERROR for unhandled exceptions, provider failures, and database errors.

## 8. Rate limiting

- Rate limiting is route-scoped, not a global middleware. The documented current limits apply independently to `/api/auth/register` and `/api/auth/login` at 5 requests/minute/IP.
- `RateLimiter` is an interface. The current `InMemoryRateLimiter` is process-local; no distributed Redis backend is assumed.
- Do not trust `X-Forwarded-For` or similar client-supplied headers for rate-limit identity until a trusted reverse-proxy configuration exists.
- Tests touching rate-limited endpoints should use the established test fixture that resets limiter state.

## 9. Testing and completion criteria

- Meaningful business logic requires tests, including validation, upsert, and error paths.
- Do not call a task complete without running the relevant checks.
- Backend checks include pytest, Ruff lint, and Ruff format check.
- Frontend checks include `npm run build` and `npm run lint`.
- Do not weaken tests merely to make them pass. Understand the cause of a failure before changing tests or implementation.
- Report test results accurately, including warnings and failures.

## 10. Multi-agent and contributor discipline

- Read `ARCHITECTURE.md` and relevant `docs/decisions/` before changing an unfamiliar module.
- Do not trust another agent's report without verifying the actual repository state, imports, contracts, dependencies, integration, tests, and regressions.
- Document deviations: what changed, why, alternatives considered, and impact.
- Record approved architecture decisions in `docs/decisions/NNNN-title.md`.
- Preserve user changes. Do not reset, overwrite, delete, commit, or push without explicit authorization.

## 11. Current known limitations

- The email sender currently documented as `memory` stores messages in an in-process outbox; it does not send real email.
- Task 11 — Email Verification — remains pending.
- Task 14 — Admin / Content Management — is not implemented.
- Task 15 — Deployment, Portability and Production Readiness — remains pending.
- The current in-memory rate limiter is process-local and is not a distributed limiter.
- Telegram integration, recommendation systems, and adaptive streaming are not implemented.

These limitations are not permission to remove roadmap items. Update this section only when the corresponding work has been implemented, tested, and verified.



qoshimcha agar malumotlar kam bo'lsa 

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

## Password reset

- **Redeeming a token is one transaction.** Spending the token, changing the
  password, expiring other reset links, and revoking the user's refresh
  sessions all live in `PasswordResetTokenRepository.consume_and_reset_password`
  and commit together. Don't split them across commits, and don't use
  `mark_used_if_active` for a reset - it commits on its own and would spend the
  token before the password changes.
- **Never log a raw reset token, a reset URL, a password, or an email body.**
  The body contains the link. Log user ids and exception *types* only.
- **`forgot-password` must stay response-identical** for registered,
  unregistered, and inactive addresses - including when email delivery fails
  (the service contains that failure). Don't add a branch that makes any of
  these cases observable to the client.
- **The reset link carries the token in the URL fragment (`#token=`), never a
  query string,** and the frontend keeps it in component state only - never in
  web storage.
- **Email goes through the `EmailSender` interface.** No real vendor exists yet;
  adding one means a new implementation plus a factory branch. Tests read reset
  links from the in-memory outbox, which `tests/backend/conftest.py` clears
  automatically between tests.

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

