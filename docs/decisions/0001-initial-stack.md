# 0001 - Initial technology stack

Status: Accepted
Date: 2026-09-13

## Context

The brief required a reasonable, justified stack to be chosen where one
wasn't already decided, documented in `ARCHITECTURE.md`/here rather than
just picked silently, and treated as an MVP choice rather than trying to
support every reasonable alternative.

## Decisions

### Backend: Python + FastAPI

FastAPI gives request/response validation (Pydantic), dependency injection
(used throughout for the service/repository wiring), and automatic OpenAPI
docs, with an async-capable ASGI server (Uvicorn) if needed later. The
target repository structure specified in the brief (`app/api`, `app/core`,
`app/schemas`, `main.py`, `requirements.txt`) is itself a FastAPI-shaped
layout, which confirmed this choice rather than, say, Django or Node/Express.

### ORM + migrations: SQLAlchemy 2.0 + Alembic

The standard, most widely supported pairing for FastAPI. SQLAlchemy's engine
abstraction is what makes the SQLite-now/PostgreSQL-later path (below)
possible without an ORM swap.

### Database: SQLite for local development

Chosen so the foundation runs with zero external infrastructure - no
container, no separately running DB server. `DATABASE_URL` is the only
thing that changes to point at PostgreSQL in a real deployment (e.g.
`postgresql+psycopg2://...`); nothing in models/repositories/services is
SQLite-specific except one `connect_args` line in
`app/core/database/session.py` that's a no-op for other engines.
**Alternative considered:** PostgreSQL from day one. Rejected for *this*
phase only because it would require provisioning a DB server before the
foundation could even be validated, with no corresponding benefit yet -
revisit before any real deployment; PostgreSQL is the intended production
target.

### Auth: JWT + Argon2id

JWT because the frontend is a separate SPA making cross-origin-capable API
calls, not server-rendered pages with cookie sessions. Argon2id (via
`passlib`, `argon2-cffi` backend) because it's OWASP's current recommended
default for password hashing.

**Note:** the original implementation used `passlib`'s bcrypt scheme.
During validation, every hash/verify call failed with
`ValueError: password cannot be longer than 72 bytes` - not because any
real password was too long, but because `passlib` 1.7.4 (unmaintained
since 2020) runs an internal self-test against a fixed reference hash, and
that self-test itself breaks under `bcrypt>=4.1`'s stricter input
handling. This is a known ecosystem incompatibility, not a bug in this
codebase. Switched to Argon2id rather than pinning `bcrypt` to an old
version, since it sidesteps the unmaintained-library risk entirely and is
the currently-preferred algorithm anyway. See `app/core/security/auth.py`.

### API style: REST

Matches the brief's own `api/{auth,anime,episodes,...}` structure directly.
GraphQL was not considered a fit - no client here needs partial/nested
querying yet, and REST endpoints map one-to-one onto the modular-monolith
service boundaries already in place.

### Package managers: pip (`requirements.txt`) + npm

`requirements.txt` because the brief's backend layout specified it
explicitly (rather than Poetry/pipenv). npm because it's the default for a
Vite project and needs no extra tooling.

### Frontend: Vite + React + TypeScript (SPA, no meta-framework)

The brief's frontend layout (`src/app`, `src/pages`, `src/components`,
`src/features`, `src/services/api`, `src/hooks`, `src/types`) doesn't
require server-side rendering or file-system routing, and nothing in the
brief calls for SEO or a server-rendered first paint. Next.js would add a
server runtime and routing conventions (`app/` vs `pages/` router) that
aren't needed yet and would need a rendering-strategy decision (which
pages are static/SSR/client) that's out of scope for a foundation.
**Alternative considered:** Next.js. Deferred, not ruled out - if SEO for
public catalog/detail pages becomes a real requirement, that's a good
reason to revisit this decision specifically (see "not yet decided" list
in `ARCHITECTURE.md`/`README.md`).

### Frontend linting: oxlint (project default, not chosen by us)

`npm create vite@latest -- --template react-ts` in the environment this was
built in scaffolds with `oxlint` rather than ESLint out of the box. Used
as generated rather than replaced with ESLint, since it already covers the
relevant React-hooks correctness rules and adding a second linter
alongside it would be redundant tooling for no benefit.

## What is deliberately left undecided

- **Production deployment target** (VPS, container platform, PaaS). No
  code depends on this decision yet; revisit when there's an actual
  deployment to do.
- **CI/CD.** Not set up. The validation steps in this ADR's sibling
  commands (`pytest`, `ruff`, `npm run build`, `npm run lint`) are exactly
  what a CI pipeline would run first - wiring them into GitHub
  Actions/etc. is a small, independent follow-up.
- **Real anime-metadata and video-source vendors.** Deliberately still
  mocked - see `ARCHITECTURE.md` sections 5-6.
