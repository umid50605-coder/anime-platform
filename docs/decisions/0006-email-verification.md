# 0006 - Email verification

Status: Accepted
Date: 2026-11-15

## Context

New accounts could register with any address and immediately use every
account feature. Task 11 adds an emailed, single-use verification link, a
resend path, and a policy for unverified accounts - without locking out
existing users and without touching Password Reset (Task 10, closed).

## Decisions

**Storage.** `users.email_verified_at` (nullable, UTC) is the single source of
truth; `NULL` = unverified. Tokens live in their own table
`email_verification_tokens` (same shape as `password_reset_tokens`, but a
separate table, repository and service - nothing is shared with Task 10).
Only a SHA-256 of the token is stored. Raw token = `secrets.token_urlsafe(32)`
(256 bits). Expiry: 24 h (`EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES`).

**Existing users.** The migration (`b3d1c8a47e52`, on top of `6e4b7f9c2a11`)
backfills `email_verified_at = created_at` for every user that exists at
upgrade time, so nobody loses access to features they already use.

**Account policy (approved).**

| | Unverified | Verified |
|---|---|---|
| Register, login, refresh, logout, `/users/me` | yes | yes |
| Public catalog, episodes, stream/content | yes | yes |
| Favorites, watch progress, watch history | **403** `email_not_verified` | yes |

Rationale: the smallest policy that protects features needing a trustworthy
email, with no change to login/JWT/refresh/logout and no dead-end signup
(registration still auto-signs the user in). The 403 body is
`{"detail": {"code": "email_not_verified", "message": "..."}}`; enforcement is
`get_verified_user` in `api/deps.py`, which reads current DB state, so
verification takes effect immediately with the same access token.

**Endpoints.**
`POST /api/auth/verify-email {token}` -> 200, or one generic 400 for unknown,
expired, used or inactive-user tokens. `POST /api/auth/resend-verification
{email}` -> always 202 with a fixed message. Both are limited to 5/min/IP with
their own counters (existing `rate_limited`). `POST /api/auth/register` is
unchanged except that `UserRead` gains `email_verified` and a verification
email is sent.

**Verification transaction** (`consume_and_verify`): lock the user row first,
conditionally spend the token (unused AND unexpired), set
`email_verified_at` (kept if already set; active users only), expire the
user's other outstanding tokens, commit once; any failure rolls everything
back, so a token is never spent while the account stays unverified. Lock order
is always user -> token. Verified on MySQL 8 with 12 racing threads: exactly
one winner, no deadlock.

**Resend limits.** Per IP (above) plus per ACCOUNT in the database: a 60 s
cooldown and at most 5 sends/hour, computed from the token table - no new
infrastructure. Throttled, unknown, inactive and already-verified outcomes are
indistinguishable from success. Older links are not invalidated on resend
(an attacker could otherwise keep killing a victim's pending link); they are
all invalidated when verification succeeds.

**Resend concurrency (atomic limits).** The limits are enforced inside one
transaction in `EmailVerificationTokenRepository.issue_if_allowed`: lock the
user's row (`SELECT ... FOR UPDATE`), re-check active/unverified, check the
cooldown, check the hourly cap, insert the token, commit. Every resend for one
account therefore serialises on that row, so parallel requests cannot all pass
the checks. Properties:

- Lock order is always user -> token, the same order `consume_and_verify`
  uses, so resend and verification cannot deadlock (tested on MySQL).
- The email is sent only after the commit, so no database lock is held while
  waiting for SMTP (tested on MySQL). A rejected request sends nothing.
- The open transaction is ended before locking. On MySQL (REPEATABLE READ) a
  plain SELECT earlier in the same transaction - the user lookup that precedes
  a resend - pins the snapshot, and the later count queries would not see a
  token another request committed while we waited for the lock. Without this
  step the lock alone does not fix the race.
- The token timestamp is taken after the lock is acquired.
- Other users' rows are untouched, so different accounts do not block each
  other (tested on MySQL).
- No new table, no advisory locks, no worker: the existing `users` row is the
  serialisation point.

**Email delivery.** `SmtpEmailSender` (stdlib `smtplib`, timeout, STARTTLS or
implicit TLS, optional login) selected with `EMAIL_PROVIDER=smtp`; config via
`SMTP_HOST/PORT/USERNAME/PASSWORD/USE_TLS/USE_SSL/TIMEOUT_SECONDS`,
`EMAIL_FROM_ADDRESS`, `EMAIL_FROM_NAME`. `send()` raises on any failure
(connect, TLS, auth, timeout, refused recipient). Delivery is synchronous: a
failure is logged by exception TYPE only and contained - registration still
succeeds and the user can resend. No outbox/worker was added: a failed send
is recoverable by the user and nothing is lost; revisit if delivery volume
grows. `memory` stays the default and sends nothing.

**Logging.** Request-ID logging is used as-is. Logs carry user ids and
exception types; never raw tokens, link URLs or message bodies.

## Known limitations

- **Timing side-channel on resend (W5, not fixed).** The public response body
  and status of `POST /api/auth/resend-verification` are identical for every
  address, but response TIME is not: an unknown address returns after one
  lookup, while an existing, unverified account also takes the row lock, a
  token insert and a **synchronous SMTP send**, which dominates the
  difference. An attacker who measures latency can therefore distinguish the
  cases despite the generic body. This is an accepted limitation, not a
  solved problem. Artificial sleeps were rejected as unreliable, and an
  outbox/worker (which would remove SMTP from the request path) was out of
  scope. The 409 on duplicate registration (below) is a larger, direct
  enumeration channel, so this one does not change the overall enumeration
  posture.

- Registering an already-registered email still returns **409** (existing
  contract, unchanged by decision). This remains an account-enumeration leak.
- Registration returns 201 whether or not the email was delivered.
- Per-IP limiting is in-process (ADR 0004); per-account limits are DB-backed.
- Synchronous SMTP adds delivery latency to register/resend requests (and
  is the main contributor to the timing difference above).
- MySQL `DATETIME` has no fractional seconds and rounds, so a stored
  `created_at` can sit up to ~0.5 s ahead of the clock; the effective 60 s
  cooldown can therefore be up to ~60.5 s. Harmless in practice.
- SMTP was tested against a fake only - never a real mail server.
- A verification link for an inactive account is treated as invalid.
