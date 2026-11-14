# 0005 - Password reset

Status: Accepted
Date: 2026-10-31

## Context

Users who forget their password had no recovery path. The brief required a
complete workflow - forgot-password, an emailed single-use token, a
reset-password endpoint, invalidation of the user's refresh sessions - with no
account-existence leak, no raw secrets stored or logged, and a transaction
design under which a token can never be spent while the password stays
unchanged.

## What existed before this task (verified in source, not assumed)

| Piece | State |
|---|---|
| `models/password_reset_token.py` | Complete (`token_hash` unique+indexed, `expires_at`, `used_at`). Reused unchanged. |
| Migration `25f3b8c1d7a4` | Complete and correct. Single linear chain `fc496559187a -> 9008fabc19fe -> 25f3b8c1d7a4`; applies on a fresh DB and `alembic check` reports no drift against the models. **No new migration was needed.** |
| `core/security/auth.py` helpers | `create_password_reset_token`, `hash_password_reset_token` present and correct. Reused. |
| `password_reset_token_expire_minutes` setting (30) | Present. Reused. |
| `PasswordResetTokenRepository` | `create`, `get_by_token_hash`, `mark_used_if_active`. **Unsuitable for the reset itself**: `mark_used_if_active` commits on its own, so using it would spend the token before the password changes. Left untouched (it has its own tests). |
| Service, endpoints, schemas, email, frontend, rate limits | Did not exist. |

## Decisions

### One transaction for the whole redemption

`PasswordResetTokenRepository.consume_and_reset_password` performs, in a
single transaction: (1) consume the token with one conditional `UPDATE ...
WHERE token_hash = ? AND used_at IS NULL AND expires_at > now`; (2) set the
user's password hash (active users only); (3) expire the user's other
outstanding reset links; (4) revoke every refresh session of the user. Any
failure rolls back all four - including step 1 - so the token is never spent
while the password is unchanged.

Single use under concurrency is delegated to the database: of N simultaneous
requests with one token, exactly one `UPDATE` matches a row. There is no
read-then-write window in Python to race through.

Why one repository method rather than the service orchestrating several
non-committing repository calls: services must not touch a `Session`
(PROJECT_RULES.md layering), so service-level transaction control would have
needed commit/rollback leaking upward. A multi-statement atomic operation
inside one repository method already has precedent (`RefreshSessionRepository.
rotate`). The Argon2 hash is computed in the service *before* the transaction
opens, so the slow step never holds a database transaction (and response time
does not depend on token validity).

Revoking all sessions also invalidates the user's live access tokens
immediately, because protected requests already verify their session family is
active (Task 9).

### No account enumeration

`POST /api/auth/forgot-password` returns `202` with identical status and body
for a registered, unregistered, or inactive address, and a failure to deliver
the email is caught inside the service (only the exception *type* is logged) -
otherwise a delivery error, which can only happen for real accounts, would
itself be the oracle. `POST /api/auth/reset-password` returns one generic `400`
for unknown, expired, and already-used tokens.

### Reset link carries the token in the URL fragment

`<frontend_base_url>/reset-password#token=...`. Browsers never send a fragment
to any server, so the token cannot land in access logs or Referer headers. The
SPA reads it into component state (never web storage) and immediately scrubs it
from the address bar with `history.replaceState`.

### Email: interface + in-memory implementation

`app/integrations/email` mirrors the provider pattern (interface, one
implementation, cached factory, selected by `email_provider`). Only
`InMemoryEmailSender` exists - a bounded in-process outbox that delivers
nothing. No real vendor dependency was added. **Password reset therefore cannot
reach real users until a real `EmailSender` is implemented** (see limitations).
The factory logs a warning if the in-memory sender is used in production.

### Rate limiting

The existing `rate_limited(...)` dependency, per IP, 5 requests/minute on each
of `forgot-password` and `reset-password`, each with its own counter, matching
the register/login/refresh convention. The rate-limit numbers are a project
convention carried over, not derived from a standard.

### Password bounds

The project has **no** pre-existing password policy (`UserCreate.password` is an
unconstrained `str`), so there was nothing to reuse. `ResetPasswordRequest`
requires 8-128 characters: a reset must not be able to set an empty password,
and the upper bound keeps arbitrarily large input away from Argon2. Registration
was deliberately **not** changed (out of scope, and would alter existing
behavior); see limitations.

### Other outstanding links die on success - but not on request

When a reset succeeds, the user's other unused reset links are expired in the
same transaction, so an older intercepted email can't be replayed. Issuing a new
link deliberately does **not** invalidate earlier ones: otherwise anyone who can
call forgot-password for a victim's address could keep killing the link the
victim is about to click (a griefing vector).

## Alternatives rejected

- **Non-committing repository methods + service-level commit.** Leaks
  transaction control into the service layer (see above).
- **Reusing `mark_used_if_active`.** Commits independently of the password
  change - the exact failure the brief forbids.
- **FastAPI `BackgroundTasks` to send the email** (to hide timing differences).
  Yield-dependency teardown closes the request's DB session before background
  tasks run in current FastAPI, which makes this fragile; with an in-memory
  sender the timing difference is also negligible. Revisit with a real sender.
- **Token in the query string.** Reaches server logs and Referer.
- **Invalidating earlier links on every new request.** Griefing vector, above.

## Known limitations

- **No email is actually delivered.** Needs a real `EmailSender`.
- **Response-time side channel.** For a registered address the endpoint does
  extra work (insert + send). Negligible with the in-memory sender; once a
  network sender exists, dispatch it asynchronously.
- **Registration still reveals existence** (`409` on a duplicate email) - a
  pre-existing behavior that undermines the generic forgot-password response
  for anyone willing to call `/register`.
- **Password policy mismatch:** resets enforce 8-128 characters; registration
  enforces nothing. Recommend one shared policy in a separate task.
- **Rate limits are per-IP only** (no per-email cap), and per-process in memory,
  as decided in Task 8: one attacker address can't flood, but many addresses can
  still send reset mail to one victim.
- **Expired/used token rows are never purged.** No housekeeping job exists.
- **Reload on the reset page loses the token** (it is scrubbed from the URL by
  design); the user must reopen the emailed link.
- **PostgreSQL READ COMMITTED edge case:** a refresh that commits at the same
  instant as a reset could leave one new refresh row the reset's revoke
  statement did not see. Not reproducible on SQLite (writers serialize); would
  need a `SELECT ... FOR UPDATE` on the user row on PostgreSQL.

## Testing

`tests/backend/test_password_reset_endpoints.py`,
`test_password_reset_atomicity.py`, `test_email_integration.py` (40 tests):
generic responses, hash-only storage, success path, invalid/expired/used tokens
being indistinguishable, session and access-token revocation, no effect on other
users, log hygiene (raw token, link, passwords never logged), rate limits,
injected database failure at each of three points in the transaction (token
stays unspent, password and sessions unchanged, same link works on retry), and
8 real threads racing one token through separate connections (exactly one
wins). The tests were mutation-checked: deliberately breaking the
implementation (premature commit, missing single-use guard, revoking the wrong
user's sessions, logging the raw token, an enumeration oracle) makes the
relevant tests fail.
