# Anime Platform — Project Handoff Report

**Updated:** 2026-11-06  
**Purpose:** This document lets another AI or developer continue the project without relying on a previous chat history. Read it before changing code.

## 1. Project summary

`anime-platform` is an anime viewing platform with a FastAPI backend and a React/Vite/TypeScript frontend.

- Backend: FastAPI, SQLAlchemy 2.x, Alembic, Pydantic, PyMySQL.
- Frontend: React, Vite, TypeScript.
- Primary database: MySQL 8.x.
- Alternative database: SQLite, used in isolated backend tests.
- Architecture: modular monolith.
- Backend flow: Router -> Service -> Repository -> Model/Database.

Metadata (`AnimeProvider`) and video streaming (`VideoProvider`) are separate domains. Do not merge their interfaces.

## 2. Task status

| Task | Name | Status | Notes |
| --- | --- | --- | --- |
| 1-6 | Foundation | Complete | Initial backend, frontend, database and provider architecture. |
| 7 | Request ID logging | Complete | Request correlation and logging are implemented. |
| 8 | Authentication | Complete | Register/login, JWT, Argon2id and rate limiting. |
| 9 | Refresh token lifecycle | Complete | Rotation, server-side logout and frontend auth restore. |
| 10 | Password reset | Awaiting audit/integration | Treat Claude-delivered code as unverified until independently reviewed and tested. Do not modify its code before the audit. |
| 11 | Email verification | Awaiting implementation/audit | Must stay separate from Task 12 and be reviewed after delivery. |
| 12 | Configurable Anime Data Source + MySQL Integration | Complete and verified | Full verification details are in section 3 and `docs/tasks/TASK_12_PROGRESS.md`. |
| 13 | Local video streaming | Complete | VideoProvider, local files, Range support and watch integration must remain compatible. |
| 14 | Admin Panel | Not started | Implement only after Tasks 10 and 11 are audited. |
| 15 | Deployment, portability and production readiness | Not started | Final functional task before project-wide final audit. |

## 3. Task 12 final verification

Task 12 is complete.

- MySQL is the primary database configuration.
- SQLite remains an explicit alternative and backend tests use isolated in-memory SQLite databases.
- `AnimeProvider` is configurable and supports `mock` and `jikan`.
- Provider metadata is normalized before it reaches the application.
- `anime_external_ids` keeps provider/external-ID mappings separate from the platform's internal IDs.
- Anime and episode repeated imports are idempotent.
- Alembic migration head: `6e4b7f9c2a11`.
- Full backend regression: **79 passed, 4 warnings**.
- Frontend TypeScript build and Vite production build passed.
- Oxlint completed with **0 errors** and 6 existing `react(set-state-in-effect)` warnings.
- MySQL migration was checked before and after `alembic upgrade head` and was at `6e4b7f9c2a11 (head)`.
- `backend/test_mysql_task12_import.py` verified on MySQL that two imports create exactly one anime, one external-ID mapping and two episodes; it cleans up its uniquely named temporary records.
- `git diff --check` passed during final verification.

### Jikan live API limitation

Live Jikan verification did not complete because the verification network could resolve `api.jikan.moe` but could not establish TCP connectivity to `api.jikan.moe:443`. General HTTPS worked, while Jikan IPv4 timed out and IPv6 was unavailable. This is a network limitation, not a confirmed application defect. The Jikan adapter implements timeout, HTTP-error, rate-limit and response-validation handling.

To retest Jikan when the network permits:

```bash
curl -4 --connect-timeout 10 --max-time 20 -sS \
  -o /tmp/jikan-anime-1.json \
  -w "HTTP_STATUS=%{http_code}\\n" \
  https://api.jikan.moe/v4/anime/1/full
```

An `HTTP_STATUS=200` result permits a read-only application-adapter check.

## 4. Configuration and secrets

The root `.env.example` is the safe configuration template committed to Git. It declares MySQL as the primary database and SQLite as an alternative.

The real local configuration is `backend/.env`:

```bash
cd ~/anime-platform/backend
cp ../.env.example .env
chmod 600 .env
```

Replace `CHANGE_ME` only in the local `DATABASE_URL` with the real MySQL password. Never commit `backend/.env`, credentials, tokens or private URLs.

Confirm the local file is ignored before every commit:

```bash
cd ~/anime-platform
git check-ignore backend/.env
```

## 5. Required workflow for remaining tasks

1. Start every task with `git status --short --branch` and `git diff --check`.
2. Read this report and the relevant task specification before coding.
3. Keep the existing layering and dependency injection in `backend/app/api/deps.py`.
4. Do not rewrite working authentication, Task 12 provider/import logic, or Task 13 streaming code without a demonstrated regression.
5. Audit Task 10 and Task 11 independently after Claude delivers them.
6. Run tests relevant to each change, then run the full regression before closing a task.
7. Update this report, the task progress file and README/architecture documents when a task materially changes configuration or architecture.
8. Do not commit, push, reset, clean or delete data without explicit user authorization.

## 6. Standard verification commands

Backend regression:

```bash
cd ~/anime-platform
PYTHONPATH=backend backend/.venv/bin/python -m pytest tests/backend
```

Frontend verification:

```bash
cd ~/anime-platform/frontend
./node_modules/.bin/tsc -b
./node_modules/.bin/vite build
./node_modules/.bin/oxlint
```

MySQL migration status:

```bash
cd ~/anime-platform/backend
export PYTHONPATH=.
./.venv/bin/alembic current
./.venv/bin/alembic upgrade head
./.venv/bin/alembic current
```

Task 12 MySQL import idempotency check:

```bash
cd ~/anime-platform/backend
export PYTHONPATH=.
./.venv/bin/python test_mysql_task12_import.py
```

Git pre-commit check:

```bash
cd ~/anime-platform
git diff --check
git status --short --branch
```

## 7. Project completion definition

The project is complete under the current plan only when:

1. Tasks 10 and 11 are delivered, independently audited and integrated.
2. Task 14 Admin Panel is implemented and verified.
3. Task 15 deployment and production-readiness requirements are implemented and verified.
4. A final project-wide backend regression, frontend build/lint, migration and deployment verification pass.
5. README, architecture documentation, this handoff report and task progress files accurately describe the final state.
