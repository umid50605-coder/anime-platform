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

## 13. Deviations from the brief's exact file layout

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
