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

## Status

This is a **foundation**, not a finished product - see
`ARCHITECTURE.md` section 9 for an explicit list of what's intentionally
not built yet, and `docs/decisions/0001-initial-stack.md` for what
technology decisions are still open.
