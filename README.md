# Anime Platform

A web platform for browsing an anime catalog, viewing anime details and episodes, and watching episodes with resume support.

The project uses a **React + TypeScript SPA** frontend and a **FastAPI modular-monolith** backend.

See:
- [`ARCHITECTURE.md`](ARCHITECTURE.md) for system structure, responsibilities, current implementation, and roadmap.
- [`PROJECT_RULES.md`](PROJECT_RULES.md) for mandatory development and contribution rules.

## Current project state

This repository is an evolving project foundation, not a finished production product.

### Implemented

- React, Vite, and TypeScript frontend.
- FastAPI modular-monolith backend.
- Repository/service/API layering and centralized dependency wiring.
- Public anime browsing and watching flow that does not require authentication.
- Account-scoped features such as favorites, watch progress/history, and profile.
- JWT authentication with Argon2id password hashing.
- Request-ID correlation and structured request-boundary logging.
- Route-scoped authentication rate limiting for registration and login.
- Refresh-session rotation, server-side logout, and frontend session restoration.
- Password-reset flow at the application level.
- Configurable anime metadata provider architecture, including Mock and Jikan adapters.
- Video provider abstraction and local video streaming work documented as Task 13.

### Not implemented / still planned

| Task | Name | Status |
|---|---|---|
| Task 11 | Email Verification | PENDING — separate task; not implemented |
| Task 14 | Admin / Content Management | NOT IMPLEMENTED |
| Task 15 | Deployment, Portability and Production Readiness | PENDING — separate task |

Other capabilities that are not currently implemented include Telegram integration, adaptive streaming, recommendation systems, and a real production email-delivery provider. See `ARCHITECTURE.md` for the current boundaries and known limitations.

**Do not treat Task 11, Task 14, or Task 15 as removed from the roadmap.** Their pending status is intentional project information and must be preserved when this document is edited.

## Technology and prerequisites

- Python 3.12+
- Node.js 20+ and npm
- MySQL 8.x as the primary/deployment database
- SQLite as an alternative for local development and isolated tests
- FastAPI, SQLAlchemy 2.x, Alembic, pytest, Ruff
- React, Vite, TypeScript, oxlint

The older SQLite-development / PostgreSQL-ready description is superseded by the current MySQL-primary strategy. Do not silently revert the database description.

## Backend setup

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp ../.env.example .env
# Configure DATABASE_URL and credentials for your local MySQL instance.
# SQLite may be selected explicitly when needed.

export PYTHONPATH=.
./.venv/bin/alembic upgrade head
./.venv/bin/python scripts/seed_mock_data.py  # optional sample data
./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Backend:
- API: `http://127.0.0.1:8000`
- Interactive API docs: `http://127.0.0.1:8000/docs`
- Health check: `http://127.0.0.1:8000/health`

Use the database URL configured for the environment. Never run migrations against production or valuable user data without an explicit approved deployment procedure.

### Backend checks

```bash
cd backend
export PYTHONPATH=.

./.venv/bin/ruff check app scripts
./.venv/bin/ruff format --check app scripts

cd ..
PYTHONPATH=backend backend/.venv/bin/python -m pytest
```

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

The frontend normally runs at `http://127.0.0.1:5173`. Its API base URL is configured through the frontend environment file.

### Frontend checks

```bash
cd frontend
npm run build
npm run lint
```

## Project layout

```text
anime-platform/
├── frontend/       React + TypeScript SPA
├── backend/        FastAPI modular monolith
├── tests/          Automated tests
├── docs/
│   └── decisions/  Architecture Decision Records
├── ARCHITECTURE.md
├── PROJECT_RULES.md
└── .env.example
```

The backend follows the general direction:

```text
API Routers
    -> Services
        -> Repositories / Integrations
            -> Database / External Providers
```

`app/api/deps.py` is the central dependency-wiring location. Frontend components communicate with the backend through `frontend/src/services/api/`; they should not make direct `fetch()` calls.

## Anime metadata provider

The metadata integration is behind the `AnimeProvider` interface. The supported implementations documented in the current architecture are:

- `mock` — deterministic local/test provider.
- `jikan` — read-only external metadata adapter.

The provider is selected through backend configuration. To select Jikan:

```env
ANIME_PROVIDER=jikan
```

To select the mock provider:

```env
ANIME_PROVIDER=mock
```

Jikan provides anime metadata; it is not a video-streaming provider. Keep metadata and video-provider responsibilities separate.

## Video provider and local streaming

Video access is isolated behind the `VideoProvider` boundary. Task 13 — Video Provider and Local Streaming — is recorded as completed in the project roadmap. Do not infer additional vendor integrations, adaptive streaming, or HLS/DASH support unless they are confirmed by the current code and architecture documentation.

## Authentication and public access

The public browsing and watching flow is intentionally available without signing in:

- Home and catalog
- Anime details
- Episode lists
- Search
- Watching/stream access

Account-scoped operations remain authenticated, including favorites, watch progress/history, and the current-user profile.

## Password reset

The application-level password-reset flow is implemented.

### API

| Endpoint | Purpose |
|---|---|
| `POST /api/auth/forgot-password` | Accepts an email address and returns a generic response that does not reveal whether the account exists. |
| `POST /api/auth/reset-password` | Redeems a reset token and sets a new password. |

Password requirements: 8–128 characters.

### Frontend routes

- `/forgot-password`
- `/reset-password#token=...`

The token is carried in the URL fragment, not a query string, and is kept in frontend component state rather than web storage.

### Configuration and delivery limitation

- `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` controls token lifetime; the documented default is 30 minutes.
- `FRONTEND_BASE_URL` is used to construct the reset link.
- `EMAIL_PROVIDER` selects the email sender implementation.

The `EmailSender` abstraction exists, but the current `memory` implementation records messages in an in-process outbox. **It does not deliver real email.** This limitation also affects future email-verification work: Task 11 must account for the absence of a production email sender rather than assuming delivery already works.

The password-reset token table was introduced by migration `25f3b8c1d7a4`. See `docs/decisions/0005-password-reset.md` for transaction and security details.

## Roadmap — preserve these entries

The following roadmap entries are intentional and must remain in future versions of this README and the project documentation:

### Task 11 — Email Verification

**Status: PENDING.**

A separate future task. Email verification has not been implemented. The task should be planned and audited independently, including verification state, expiring single-use verification tokens, backend routes/service/repository changes where required, frontend verification/resend UI, tests, and the email-delivery dependency. Do not mark it complete merely because the `EmailSender` interface exists.

### Task 14 — Admin / Content Management

**Status: NOT IMPLEMENTED.**

The project does not currently have an admin panel/content-management feature. This remains a separate roadmap task. Its permissions, workflows, data model, API, and UI scope must be established from an approved task definition and repository audit; do not invent or implement them as part of unrelated tasks.

### Task 15 — Deployment, Portability and Production Readiness

**Status: PENDING.**

This remains a separate roadmap task. The project architecture documentation previously recorded that no production deployment target, containerization strategy, or CI/CD pipeline had been selected. The task must assess and define the required deployment and portability work before implementation. Do not claim production readiness based only on local development instructions.

## Explicitly out of scope unless a future task approves them

- Telegram bot/channel integration.
- Adaptive streaming (bitrate switching, bandwidth estimation, buffer control, prefetching).
- Recommendation systems.
- Message queue or distributed infrastructure such as Redis/Kafka without a demonstrated requirement.
- Real production email delivery until a provider is selected and integrated.
- Additional metadata/video vendors beyond those confirmed in the codebase.

These exclusions do not cancel Tasks 11, 14, or 15. They define current implementation boundaries while the roadmap remains active.





# Anime Platform

A web platform for browsing an anime catalog, viewing details/episodes, and
watching with resume support - built as a modular monolith backend (FastAPI)
with a separate React SPA frontend. See `ARCHITECTURE.md` for the design and
`PROJECT_RULES.md` for working rules. Telegram, an admin panel, and adaptive
streaming are out of scope for this phase (see `ARCHITECTURE.md` section 9).

Anime metadata and video streaming both come from external providers,
accessed through interfaces (`AnimeProvider`, `VideoProvider`) with a mock
implementation each - see `ARCHITECTURE.md` sections 5-6. No real vendor is
wired in yet.

## Prerequisites

- Python 3.12+
- Node.js 20+ and npm
- No external database server needed - local dev uses SQLite.

## Backend setup

```bash
cd backend
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp ../.env.example .env   # then edit backend/.env if you need non-default values

export PYTHONPATH=.
./.venv/bin/alembic upgrade head        # creates anime_platform.db with all tables
./.venv/bin/python scripts/seed_mock_data.py   # optional: adds 2 sample anime + episodes

./.venv/bin/uvicorn app.main:app --reload --port 8000
```

Backend is now running at `http://127.0.0.1:8000`. Interactive API docs:
`http://127.0.0.1:8000/docs`. Health check: `http://127.0.0.1:8000/health`.

### Backend checks

```bash
cd backend
export PYTHONPATH=.
./.venv/bin/ruff check app scripts       # lint
./.venv/bin/ruff format --check app scripts   # format check
cd ..
PYTHONPATH=backend backend/.venv/bin/python -m pytest   # tests (run from repo root)
```

## Frontend setup

In a second terminal:

```bash
cd frontend
npm install
cp .env.example .env   # defaults already point at http://127.0.0.1:8000

npm run dev
```

Frontend is now running at `http://127.0.0.1:5173` (Vite's default port -
the backend's default CORS config expects this exact origin; see
`backend/app/core/config/settings.py` if you change it).

### Frontend checks

```bash
cd frontend
npm run build   # tsc -b && vite build
npm run lint     # oxlint
```

## Project layout

```
anime-platform/
├── frontend/       React + TypeScript SPA (Vite)
├── backend/        FastAPI modular monolith
├── tests/          Backend tests (pytest; pythonpath configured in pytest.ini)
├── docs/
│   └── decisions/  Architecture Decision Records
├── ARCHITECTURE.md
├── PROJECT_RULES.md
└── .env.example
```

See `ARCHITECTURE.md` for what each backend layer
(`api`/`services`/`repositories`/`integrations`) is responsible for, and
`docs/decisions/0001-initial-stack.md` for why each technology was chosen.

## Sample account (after seeding)

The seed script only creates anime/episodes, not a user. Register one
through `/docs` (the `POST /api/auth/register` endpoint) or through the
frontend's Profile page.

## Password reset

| | |
|---|---|
| API | `POST /api/auth/forgot-password` (`{"email"}` -> `202`, same answer for every address), `POST /api/auth/reset-password` (`{"token", "new_password"}` -> `200`, or a generic `400`; password must be 8-128 characters) |
| Frontend | `/forgot-password` (reached from "Forgot your password?" on the sign-in form) and `/reset-password#token=...` (the emailed link) |
| Settings | `PASSWORD_RESET_TOKEN_EXPIRE_MINUTES` (default 30), `FRONTEND_BASE_URL` (where the emailed link points), `EMAIL_PROVIDER` - see `.env.example` |
| Database | No new migration: `password_reset_tokens` ships in `25f3b8c1d7a4`; `alembic upgrade head` covers it |

**No email is delivered yet.** `EMAIL_PROVIDER=memory` is the only sender; it
keeps messages in an in-process outbox (which is what the tests read) and sends
nothing, so the feature cannot reach real users until a real `EmailSender` is
added. Design, transaction guarantees, and limitations:
`docs/decisions/0005-password-reset.md`.

## Email verification

| | |
|---|---|
| API | `POST /api/auth/verify-email` (`{"token"}` -> `200`, or a generic `400`), `POST /api/auth/resend-verification` (`{"email"}` -> `202`, same answer for every address). `UserRead` now includes `email_verified`. |
| Policy | Unverified users can sign in, browse and watch, and use `/users/me`. Favorites and watch progress/history return `403` with `detail.code = "email_not_verified"` until verified. Users that existed before the migration are backfilled as verified. |
| Frontend | `/verify-email#token=...` (the emailed link); the Profile page shows a "Verify your email" panel with a resend button for unverified users. |
| Settings | `EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES` (default 1440), `EMAIL_VERIFICATION_RESEND_COOLDOWN_SECONDS` (60), `EMAIL_VERIFICATION_MAX_SENDS_PER_HOUR` (5), `EMAIL_PROVIDER` (`memory` or `smtp`), and for SMTP: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_USE_TLS`, `SMTP_USE_SSL`, `SMTP_TIMEOUT_SECONDS`, `EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`, plus `FRONTEND_BASE_URL` |
| Database | Migration `b3d1c8a47e52`: `users.email_verified_at` + `email_verification_tokens`; run `alembic upgrade head` |

`EMAIL_PROVIDER=memory` (the default) delivers nothing. Set `EMAIL_PROVIDER=smtp`
with the SMTP settings (via environment only) to send real mail. Design and
limitations (including the existing `409` on duplicate registration):
`docs/decisions/0006-email-verification.md`.

## Status

This is a **foundation**, not a finished product - see
`ARCHITECTURE.md` section 9 for an explicit list of what's intentionally
not built yet, and `docs/decisions/0001-initial-stack.md` for what
technology decisions are still open.


