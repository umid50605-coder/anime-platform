# 0002 - Remove authentication from the public viewing flow

Status: Accepted
Date: 2026-09-14

## Context

The initial foundation (see `0001-initial-stack.md`) built a full JWT auth
system and used it to gate the watch page/stream endpoint alongside the
genuinely account-specific features (favorites, watch progress/history,
profile). The product decision is that this platform has no account
requirement at all for browsing or watching: no login, no register, no
"please sign in" screen anywhere in the primary flow
(home → catalog → anime detail → episodes → search → watch).

## What was inspected before changing anything

**Already public, no change needed:** `GET /api/anime/`, `GET
/api/anime/{slug}`, `GET /api/episodes/anime/{anime_id}`, `GET
/api/episodes/{episode_id}`, `GET /api/search/` - none of these ever had a
`get_current_user` dependency.

**Required a change:** `GET /api/watch/{episode_id}/stream` was gated
behind `get_current_user`, and the frontend's `WatchPage` returned early
with a "Sign in to watch episodes." message for any anonymous visitor -
this was the one place actually blocking the stated public flow.

**Left alone, on purpose:** `GET`/`PUT /api/watch/{episode_id}/progress`,
`GET /api/watch/history`, all of `/api/favorites/*`, and `GET
/api/users/me`. These are inherently about a specific user's data;
"anonymous watch progress" would mean either a new anonymous-session
mechanism (explicitly ruled out as overengineering for this change) or no
real progress tracking at all. No `ProtectedRoute`/`RequireAuth`/route-guard
pattern existed on the frontend to begin with - `useAuth()` was used
per-page/per-component to conditionally show extra features, never to
block a whole page. `AnimeDetailPage`'s favorite button and
`FavoritesPage`'s empty state already followed this pattern correctly.

## Decision

1. **Backend:** removed the `current_user` dependency from the `/stream`
   handler only, in `app/api/watch/router.py`. The other three watch/*
   endpoints, `/api/favorites/*`, and `/api/users/me` are unchanged.
2. **Frontend:** removed `WatchPage`'s early-return auth gate entirely, and
   removed the "Sign in" identity link from `NavBar`. Watch progress is
   still fetched/saved when a user happens to be signed in (an unrelated,
   optional enhancement to the same page) - see the bug fix below for why
   this needed one additional change to actually work.
3. **Nothing was deleted.** `ProfilePage` (login/register UI),
   `AuthContext`/`useAuth`, the `/api/auth/*` endpoints, and the
   `users`/`favorites`/`watch_progress` DB tables and migration all remain
   exactly as built - chosen over deletion per the explicit instruction to
   pick the safest of "remove / disable / keep as a separate module" for
   account-linked features that aren't part of the public flow. `Favorites`
   stays linked in the nav (it's a content-personalization feature, not an
   auth prompt, and clicking it while signed out shows a plain informational
   line, not a login button) - `ProfilePage`'s route (`/profile`) is no
   longer linked from the nav (since its only purpose was login/register,
   which the brief asked not to expose), but the route and component were
   left in place rather than deleted.

## Bug found during validation (not present before this change - a
## consequence of making the page work for anonymous users)

`useWatchProgress(episodeId)` initialized `isLoading` to `true` and only
ever set it back to `false` inside the branch that runs when `episodeId` is
defined. Once `WatchPage` started calling it with `episodeId={undefined}`
for anonymous viewers (correct - no progress to load), the effect returned
immediately without resolving `isLoading`, so `isLoading` stayed `true`
forever and the video player never rendered for anyone without an account -
exactly the class of regression the brief's "run the tests, don't just
claim it works" instruction is meant to catch. Fixed by resolving
`isLoading` to `false` in the early-return branch too.

## Testing

Added `tests/backend/test_public_flow.py`:
- one test drives the full public flow (catalog → detail → episodes →
  search → stream) through the real FastAPI app with **no** Authorization
  header and asserts none of them return 401/403;
- one test asserts progress/history endpoints still correctly return 401
  without a token (locking in that these were *not* accidentally made
  public too);
- one test checks `/health`.

Existing `pyproject.toml` for `ruff` was backend-only
(`backend/pyproject.toml`); this pass found that `tests/` had never
actually been linted (ruff's config discovery doesn't look at a sibling
directory's config). Added a root-level `pyproject.toml` with the same
rule set and fixed the ~13 issues it found (import ordering, `Dict`/`List`/
`Optional` → `dict`/`list`/`X | None`, one unused import, one long line) -
unrelated to auth, but surfaced while re-running validation per the
brief's regression-testing instruction, so fixed rather than left for
later.

## Alternatives considered

- **Anonymous/localStorage-based watch progress**, so unauthenticated
  viewers still get resume support. Explicitly rejected for this change -
  the brief called this out by name as something not to build yet
  ("Hozir buni overengineer qilma").
- **Deleting the auth system entirely** (endpoints, models, migration).
  Rejected: the brief explicitly listed "keep as an isolated module" as an
  acceptable, safer option, and nothing about the public flow requires
  deleting it - it would also mean discarding a working, tested feature
  (favorites/progress) that only needs an account, not removal.
