# Architecture

## 1. System overview

Anime Platform is a React/Vite/TypeScript single-page application backed by a FastAPI modular monolith.

```text
USER
  |
  v
FRONTEND (React + Vite + TypeScript SPA)
  |
  v
BACKEND API (FastAPI modular monolith)
  |
  +-- OWN DATABASE (MySQL primary / SQLite alternative)
  |
  +-- ANIME METADATA (AnimeProvider: Mock / Jikan)
  |
  +-- VIDEO SOURCE (VideoProvider abstraction; implementation details
                    must be verified against the current repository)
```

The project is a modular monolith, not a set of microservices. Telegram integration, admin/content management, and adaptive streaming are not part of the current implemented system. Admin/content management remains a future roadmap task.

## 2. Frontend / backend relationship

The frontend is a Vite + React + TypeScript SPA. It communicates with the backend through `frontend/src/services/api/`:

- `client.ts` provides the shared API client.
- Domain-specific API modules handle auth, anime, episodes, watch, favorites, and health.
- Components should not call `fetch()` directly.

Authentication state is managed in the auth feature (`AuthContext` and `useAuth`). The documented implementation stores JWT state in `localStorage`. This is an MVP tradeoff with an XSS exposure; any move to httpOnly cookies and CSRF protection requires a deliberate design decision and coordinated frontend/backend changes.

## 3. Backend layers and dependency direction

```text
API routers
    |
    v
Services
    |
    v
Repositories / Integrations
    |
    v
Own Database / External Providers
```

Concretely:

```text
app/api/*/router.py
    -> app/services/*/service.py
        -> app/repositories/*/repository.py
        -> app/integrations/*
```

Responsibilities:

- **API routers:** parse requests, call services, shape responses. They do not contain business logic or direct database/provider access.
- **Services:** own business rules and orchestration. They depend on repository/provider abstractions, not SQLAlchemy sessions or vendor HTTP clients.
- **Repositories:** own database queries and persistence operations, not business rules.
- **Integrations:** adapt external systems to internal interfaces.
- **Dependency wiring:** `app/api/deps.py` is the central location that builds request-scoped dependencies.

The intended dependency direction is:

```text
Frontend -> Backend API -> Application Services
         -> Repositories / Integrations -> Database / External Providers
```

## 4. Database responsibility and strategy

The database stores platform state and mappings; it is not intended to be a full mirror of an external anime catalog.

**Current strategy:**
- **MySQL 8.x is the primary database strategy.**
- **SQLite remains an alternative for local development and isolated tests.**

An older architecture version described SQLite development and PostgreSQL readiness. That description is superseded and must not replace the current MySQL-primary strategy.

The documented tables and responsibilities include:

| Table | Responsibility |
|---|---|
| `users` | Accounts and authentication |
| `anime` | Mapping/cache for external anime identifiers and fields needed by the platform |
| `episodes` | Mapping/cache for external episode identifiers |
| `watch_progress` | Per-user episode progress; also used to derive watch history |
| `favorites` | User favorites |
| `refresh_sessions` | Refresh-session lifecycle |
| `password_reset_tokens` | Password-reset token hashes and lifecycle |

There is no separate watch-history table in the documented design: watch history is derived from `watch_progress` ordered by its update timestamp. Do not add a second table without a concrete requirement and an approved migration plan.

Anime and episode records are mappings rather than full copies of all external metadata. The provider supplies metadata through its interface; the database stores the platform-owned state and the fields needed for stable internal references and rendering.

## 5. Anime metadata provider

`AnimeProvider` defines the vendor-neutral metadata boundary. The documented operations include:

- `get_anime`
- `search_anime`
- `list_episodes`

The internal data shapes include vendor-neutral `AnimeMetadata` and `EpisodeMetadata`.

The current documented adapters are:
- **Mock provider:** deterministic implementation for local/test use.
- **Jikan provider:** read-only external metadata adapter.

The factory selects the provider through configuration (documented setting: `ANIME_PROVIDER`). A new metadata vendor should be added as a new adapter implementing the existing interface and a factory selection branch. Do not couple `AnimeService` or API routers directly to a vendor SDK or HTTP client.

Jikan is a metadata source. It does not provide video streams.

## 6. Video provider and local streaming

Video access is separated behind the `VideoProvider` boundary. The earlier architecture describes a `get_stream(external_episode_id) -> StreamInfo`-style interface and a mock provider.

**Task 13 — Video Provider and Local Streaming — is recorded as completed in the current project roadmap.** The exact implementation must be verified from the repository before changing it. Do not infer or add features such as adaptive bitrate switching, bandwidth estimation, buffer control, prefetching, HLS, or DASH unless the code and an approved requirement support them.

Keep anime metadata-provider responsibilities separate from video-provider and local-streaming responsibilities.

## 7. Authentication boundary

Authentication is optional for the core viewing flow.

Public flow:
- Home
- Catalog
- Anime detail
- Episodes
- Search
- Watch/stream

These must remain accessible without an account or an Authorization header.

Account-scoped flow:
- Favorites
- Watch progress
- Watch history
- Current-user profile

These remain authenticated and must not pull public browsing/watching behind a login wall.

## 8. Authentication and security capabilities

The documented current foundation includes:
- JWT authentication.
- Argon2id password hashing.
- Refresh-session rotation and server-side logout.
- Frontend session restoration.
- Route-scoped rate limiting for registration and login.
- Request-ID correlation and request-boundary logging.
- Application-level password reset.

### Password reset

The password-reset flow uses:
- `POST /api/auth/forgot-password`
- `POST /api/auth/reset-password`
- A `password_reset_tokens` table.
- Single-use reset tokens stored as hashes.
- A transaction that consumes the token, updates the password, expires other reset links, and revokes refresh sessions together.
- A generic forgot-password response to avoid account enumeration.
- A URL fragment (`#token=`) so the raw token is not sent as a query parameter.

The `EmailSender` interface is present, but the documented implementation is an in-memory sender. It does not deliver real email. See `docs/decisions/0005-password-reset.md` for the detailed decision and limitations.

## 9. Request correlation, logging, and rate limiting

### Request correlation and logging

The documented implementation assigns or accepts a safe request ID through `RequestContextMiddleware`. A context-aware logging setup adds the request ID to request log records.

Provider failures are logged at provider boundaries through logging decorators wired by factories. Database errors are logged centrally at the database dependency boundary. Sensitive values must not be logged.

See `docs/decisions/0003-request-correlation-logging.md`.

### Authentication rate limiting

The documented rate limiter follows an interface/factory design. The current in-memory implementation is process-local and is applied only to:
- `/api/auth/register`
- `/api/auth/login`

The documented limit is 5 requests/minute/IP for each route independently. It is not a global middleware and does not limit public browsing/watch endpoints.

No distributed Redis limiter is assumed. Do not trust forwarded client IP headers unless a trusted proxy is configured.

See `docs/decisions/0004-auth-rate-limiting.md`.

## 10. Email capability and Task 11

Email sending is abstracted behind `EmailSender`. The current documented `memory` sender records messages in an in-process outbox and is useful for tests; it is not production email delivery.

### Task 11 — Email Verification

**Status: PENDING — not implemented.**

This is a separate roadmap task. The earlier task definition identifies the likely concerns:
- User verification state/metadata.
- Verification token generation, expiry, and single-use behavior.
- Backend verification and resend routes/service logic.
- Frontend verification/resend UI.
- Tests for successful verification and expired/tampered token rejection.
- Integration with an email provider.

These are planning requirements, not a claim that the feature already exists. Before implementation, audit the current user model, auth service, email integration, database migrations, frontend auth flow, and tests. Define the exact schema and API contract before changing code.

The absence of real email delivery is a known dependency/limitation and must be addressed in the task plan.

## 11. Admin / Content Management

### Task 14 — Admin / Content Management

**Status: NOT IMPLEMENTED.**

The current architecture documentation explicitly lists the admin panel as not implemented. Task 14 remains a separate roadmap task.

No admin role model, permission matrix, content-management workflow, or admin API/UI contract is asserted here because those details have not been established by the available task definition. They must be defined through an approved requirements document and repository audit before implementation.

Do not treat the absence of an admin panel as a reason to add speculative admin abstractions to unrelated tasks.

## 12. Deployment, portability, and production readiness

### Task 15 — Deployment, Portability and Production Readiness

**Status: PENDING.**

This is a separate roadmap task. The earlier architecture records that a production deployment target, containerization approach, and CI/CD pipeline had not yet been selected.

The task must begin with an audit and an explicit deployment/portability plan. Do not claim production readiness based only on local setup instructions. Do not assume a hosting provider, container strategy, CI/CD platform, or production topology until selected and approved.

The detailed acceptance criteria and implementation sequence remain to be defined in the Task 15 plan.

## 13. Explicitly not implemented / not assumed

The following capabilities are not established as implemented by the architecture sources:

- Telegram bot/channel integration.
- Admin panel / content-management UI (Task 14).
- Adaptive bitrate streaming, bandwidth estimation, buffer controller, or prefetching.
- Recommendation systems.
- Message queue / Redis / Kafka infrastructure.
- Production email delivery.
- A selected production deployment target, containerization strategy, or CI/CD pipeline (Task 15).

These exclusions describe current implementation boundaries. They do not remove the pending roadmap tasks.

## 14. Architecture decisions and deviations

Architecture decisions should be recorded in `docs/decisions/NNNN-title.md`.

The documented decisions include:
- `0002-remove-auth-from-public-flow.md` — public browsing/watching remains unauthenticated.
- `0003-request-correlation-logging.md` — request correlation and logging boundaries.
- `0004-auth-rate-limiting.md` — route-scoped authentication rate limiting.
- `0005-password-reset.md` — password-reset flow and limitations.

The earlier architecture also records two deliberate layout deviations:
1. A `repositories/favorite/` layer was added because favorites are persisted state and require their own data-access boundary.
2. `frontend/.env.example` was added because Vite reads frontend environment variables from the frontend package root.

Preserve documented decisions unless an approved change supersedes them.

## 15. Project roadmap — authoritative status list

This roadmap is part of the project documentation and must be preserved in future edits.

| Task | Name | Current status |
|---|---|---|
| Task 10 | Password Reset | IMPLEMENTED — application-level flow; real email delivery remains unavailable |
| Task 11 | Email Verification | PENDING — separate task |
| Task 12 | Configurable Anime Data Source | COMPLETED |
| Task 13 | Video Provider and Local Streaming | COMPLETED |
| Task 14 | Admin / Content Management | NOT IMPLEMENTED |
| Task 15 | Deployment, Portability and Production Readiness | PENDING |

Task order/history matters: Tasks 12 and 13 were completed before Task 10 was finalized. Do not reorder the historical sequence or mark Tasks 11, 14, or 15 complete without implementation evidence and explicit verification.

## 16. Change discipline

Before changing an unfamiliar area:
1. Read this document and relevant Architecture Decision Records.
2. Inspect the actual repository and Git working tree.
3. Identify the exact files, contracts, and dependencies affected.
4. Separate task-related defects from unrelated technical debt.
5. Present an implementation plan and wait for approval when the task requires it.
6. Preserve user changes and avoid destructive Git/database operations.
7. Run relevant tests, lint, formatting, and build checks.
8. Report exact changes, test results, limitations, and remaining work.




# Architecture

## 1. System overview

```
USER
 |
 v
FRONTEND (React SPA)
 |
 v
BACKEND API (FastAPI, modular monolith)
 |
 +-- OWN DATABASE (SQLite dev / PostgreSQL-ready)
 +-- EXTERNAL ANIME API   (behind AnimeProvider interface - mock today)
 +-- EXTERNAL VIDEO SOURCE (behind VideoProvider interface - mock today)
```

Telegram, an admin panel, and adaptive streaming are **not part of this
codebase yet** - they were explicitly out of scope for this phase. Nothing
here assumes their eventual shape; the provider/repository boundaries exist
so they can be added later without a rewrite.

## 2. Frontend / backend relationship

The frontend is a Vite + React + TypeScript single-page app. It talks to the
backend exclusively through `frontend/src/services/api/*` - a thin fetch
wrapper (`client.ts`) plus one module per domain (auth, anime, episodes,
watch, favorites, health). No component calls `fetch()` directly. This
mirrors, on the frontend, the same "don't let callers reach past an
abstraction" principle the backend uses for external providers.

Auth state (the JWT) lives in `features/auth` (`AuthContext` + `useAuth`),
persisted to `localStorage` so a page refresh doesn't log the user out. This
is a standard MVP tradeoff: an XSS on the page could read the token from
`localStorage`. Acceptable for a foundation with no sensitive data beyond a
password (already hashed server-side) and a session token; revisit if the
threat model changes (e.g. httpOnly cookies + CSRF protection).

## 3. Backend layers

```
API (routers)              <- thin: parse request, call a service, shape response
  v
Services                    <- business logic and rules live here, nowhere else
  v
Repositories / Integrations <- data access and external providers
  v
Own Database / External Providers
```

Concretely: `app/api/*/router.py` -> `app/services/*/service.py` ->
`app/repositories/*/repository.py` (DB) or `app/integrations/*` (external).
Wiring between these layers happens in exactly one place,
`app/api/deps.py`, so a route handler never constructs a repository or
service itself - it declares a dependency and FastAPI injects it.

Rules this enforces (see also `PROJECT_RULES.md`):
- API handlers never touch the DB or a provider directly.
- Services never import SQLAlchemy or a provider's HTTP client - only
  repository/provider interfaces.
- Repositories never contain business rules, only queries.

## 4. Database responsibility

The database stores **platform state**, not external content:

| Table            | Purpose                                                         |
|-------------------|-------------------------------------------------------------------|
| `users`           | Accounts / auth                                                  |
| `anime`           | A mapping/cache to an external anime (id, slug, title, poster)   |
| `episodes`        | A mapping/cache to an external episode                           |
| `watch_progress`  | Resume position per (user, episode); also serves as watch history|
| `favorites`       | A user's favorited anime                                         |

**Deliberate design choice - no separate watch-history table.** A user's
watch history is `watch_progress` rows ordered by `updated_at`. Keeping a
second table in sync with the same information would be duplicated state
for no current benefit. If a real need for a distinct append-only history
log appears later (e.g. "rewatched on two different dates"), it can be
added without touching `watch_progress` - see `docs/decisions/`.

**Anime/Episode are mappings, not mirrors.** Each row stores
`external_provider` + `external_id` plus only the fields needed to render a
catalog/detail page without an extra network call (title, slug, poster).
Everything else (synopsis, genres, full episode metadata) is fetched live
from `AnimeProvider` on each detail request. This is what makes swapping
the metadata vendor later a provider-level change, not a schema migration.

## 5. External API responsibility (`AnimeProvider`)

`app/integrations/anime_api/provider.py` defines the `AnimeProvider`
interface (`get_anime`, `search_anime`, `list_episodes`) and a vendor-
agnostic `AnimeMetadata`/`EpisodeMetadata` shape. `mock_provider.py` is the
only implementation today - two fixture anime, used to prove the
abstraction works end-to-end (register -> catalog -> detail -> episodes ->
search all round-trip through it in the test suite and in manual
validation). `factory.py` selects the implementation via `ANIME_PROVIDER`
in settings; nothing else in the codebase imports `MockAnimeProvider`
directly except the factory.

Adding a real vendor (AniList, Jikan, etc.) later means: write a new
`AnimeProvider` subclass, add one branch in `factory.py`. `AnimeService`,
every router, and every test that uses fakes are unaffected.

## 6. Video provider responsibility (`VideoProvider`)

Same pattern, smaller surface: `get_stream(external_episode_id) ->
StreamInfo`. `MockVideoProvider` returns a deterministic placeholder URL.
No real video vendor is wired in, per scope.

**What's explicitly NOT here yet, on purpose:** adaptive bitrate switching,
bandwidth estimation, a buffer controller, prefetching. `VideoPlayer.tsx`
on the frontend is a plain `<video>` element. These are only added once a
real, measured problem exists - adding them later means adding
methods/fields to `VideoProvider`/`StreamInfo` and swapping the player
component, not restructuring how episodes/watch progress work.

## 7. Dependency direction

```
Frontend -> Backend API -> Application Services -> Repositories/Integrations -> DB/External Providers
```

Enforced by convention + code review, not a lint rule: services accept
repository/provider objects via their constructor (dependency injection),
never look them up themselves. `app/api/deps.py` is the only file that
knows how to build a fully-wired service from a request-scoped DB session.

## 8. Why a modular monolith

One deployable backend, organized into modules (`anime`, `episode`, `user`,
`watch`, `favorite`, `auth`) with clean internal boundaries, instead of
microservices. At this stage there is one team (or one set of
collaborating agents) and no independent scaling/deployment need per
module - splitting into services now would add network calls, service
discovery, and deployment complexity with no corresponding benefit. The
module boundaries inside the monolith (services/repositories/integrations
per domain) are exactly what would become service boundaries later, if
that's ever justified - so this isn't a dead end, just the appropriately
sized choice for now.

## 9. What is intentionally NOT implemented yet

- Telegram bot/channel integration (any of it - no modules, no event
  system wired to it, out of scope for this phase per the brief)
- Admin panel
- Real anime-metadata vendor and real video vendor (both are mock-only)
- Adaptive streaming (bitrate switching, bandwidth estimation, buffer
  control, prefetching)
- Recommendation systems
- Any message queue / Redis / Kafka - the "event" pattern the wider
  ecosystem plan describes (for the eventual Telegram integration) does not
  exist in this codebase yet; there is nothing to decouple from yet since
  Telegram isn't here
- Rate limiting, caching layer, background job runner
- CI/CD pipeline, containerization, production deployment target (none
  selected yet - see `docs/decisions/`)

## 10. Authentication is optional, not required for browsing/watching

**Decision (2026-09-14):** the core viewing flow (home → catalog → anime
detail → episodes → search → watch/stream) requires zero authentication
steps. This was a deliberate change from the initial build, where the
watch page and its stream endpoint were gated behind login by default
along with the genuinely user-scoped features. See
`docs/decisions/0002-remove-auth-from-public-flow.md` for the full
before/after and rationale.

What stayed authenticated, on purpose, because the data is inherently
user-scoped and can't mean anything without an account: watch progress
(`GET`/`PUT /api/watch/{episode_id}/progress`), watch history
(`GET /api/watch/history`), favorites, and `/api/users/me`. These remain
as an isolated, optional module (per `PROJECT_RULES.md`) - the rule to
avoid is letting any of them pull the main flow behind a login wall.

## 11. Request correlation and logging

Every request gets an ID (`X-Request-ID` - reused from the client if
present and safe, otherwise generated) via `RequestContextMiddleware`
(`app/core/logging/`). A contextvar-backed `LogRecordFactory` stamps every
log line anywhere in the app with that ID automatically, so services/
repositories/providers never need a `request_id` parameter threaded
through them to get correlated logs - this keeps logging a true
cross-cutting concern rather than something scattered through business
logic. Provider failures are logged by transparent `Logging*Provider`
decorators wired in only at the factory functions (never inside
`AnimeService`/`WatchService`); DB errors are logged once, centrally, in
`get_db()`. None of these change any interface, schema, or public
response contract. Full rationale, plus three real pre-existing bugs found
and fixed while validating this (a `DEBUG=true` default that leaked
tracebacks and skipped the app's own error handler, and a request-ID
context-timing bug affecting the one response path Starlette's own
`ServerErrorMiddleware` produces) are in
`docs/decisions/0003-request-correlation-logging.md`.

## 12. Auth rate limiting

`app/core/rate_limit/` follows the exact same interface-plus-factory shape
as `AnimeProvider`/`VideoProvider` (§5-6): a `RateLimiter` interface, one
concrete `InMemoryRateLimiter` implementation, a cached factory. Applied
only to `/api/auth/register` and `/api/auth/login` via `dependencies=[...]`
on those two routes - 5 requests/minute/IP each, independent of each other
- never a global middleware, so it cannot affect any other route by
construction. Known, accepted limitation: state is per-process (no
Redis/distributed backend yet). Full rationale in
`docs/decisions/0004-auth-rate-limiting.md`.

## 13. Password reset

`POST /api/auth/forgot-password` -> `PasswordResetService` creates a single-use
token (only its hash is stored in `password_reset_tokens`) and emails a link via
the `EmailSender` interface (`app/integrations/email`, same interface/factory
shape as the anime and video providers; only an in-memory implementation exists
so far). `POST /api/auth/reset-password` redeems it through
`PasswordResetTokenRepository.consume_and_reset_password`, which in ONE
transaction spends the token, sets the new password hash, expires the user's
other reset links, and revokes all of the user's refresh sessions - so a failure
anywhere leaves the token unspent and the password unchanged. Responses never
reveal whether an email is registered. Frontend routes `/forgot-password` and
`/reset-password`; the emailed link carries the token in the URL fragment so it
never reaches a server. Full rationale and limitations (notably: no real email
is delivered yet): `docs/decisions/0005-password-reset.md`.

## 14. Deviations from the brief's exact file layout

Documented transparently rather than silently changed, per project rules:

1. **`repositories/favorite/` was added.** The brief's repositories list
   was `user`, `anime`, `episode`, `watch` - it didn't include `favorite`,
   even though `services/favorite` and `api/favorites` were both specified.
   Favorites are persisted state like everything else, so they need a
   data-access layer; omitting one would have meant `FavoriteService`
   either reaching into another repository it doesn't own, or touching the
   DB directly (both against the stated rules). Added `FavoriteRepository`
   with the same shape as its siblings.
2. **`frontend/.env.example` was added** alongside the root one. Vite only
   reads `VITE_`-prefixed variables from its own `.env` file at the
   frontend package root, not from a root-level file - so a frontend-only
   example file is needed for the frontend to actually pick up
   `VITE_API_BASE_URL` when a developer copies it into `frontend/.env`.

