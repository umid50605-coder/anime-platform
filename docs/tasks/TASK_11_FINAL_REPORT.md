# Task 11 - Email Verification - Final Report

> Updated for the finalization round (W3/W4/W5). Sections 1-8 describe the
> implementation (small corrections only); **sections 9-16 report results of
> checks executed in this finalization round** - nothing from the previous round
> is reported as newly executed.

## 1. Task summary
Registration now emails a single-use verification link; users verify through
`/verify-email#token=...`, can request another email, and unverified accounts
are restricted to the approved policy (see section 2). Existing users are
backfilled as verified so nobody is locked out. Task 10 was not modified.

## 2. Architecture
`Router -> EmailVerificationService -> EmailVerificationTokenRepository -> DB`,
wired in `api/deps.py`. Email goes through the existing `EmailSender`
abstraction (new `SmtpEmailSender`). Rate limiting reuses `rate_limited` (per
IP) plus a DB-backed per-account cooldown (60 s) and cap (5/hour), enforced
atomically under a user-row lock (W3, section 15). Policy: unverified users can log in, browse/watch, and call
`/users/me`; favorites and watch progress/history return 403
`email_not_verified` via `get_verified_user`. Rationale and detail:
`docs/decisions/0006-email-verification.md`.

## 3. Modified files
Created:
- `backend/app/models/email_verification_token.py` - token model
- `backend/app/repositories/email_verification/{__init__,repository}.py` - atomic consume-and-verify
- `backend/app/services/email_verification/{__init__,service}.py` - send/resend/verify
- `backend/app/integrations/email/smtp_sender.py` - SMTP delivery
- `backend/migrations/versions/b3d1c8a47e52_add_email_verification.py` - migration
- `docs/decisions/0006-email-verification.md`, this report
- `frontend/src/pages/verify-email/VerifyEmailPage.tsx`, `frontend/src/features/auth/{ResendVerification.tsx,verificationMessages.ts}`
- `tests/backend/test_email_verification_{endpoints,smtp,migration,mysql}.py`

Modified:
- `backend/app/models/{user,__init__}.py` - `email_verified_at`, `email_verified`, model registration
- `backend/app/schemas/{auth,user}.py` - request schemas; `email_verified` in `UserRead`
- `backend/app/core/config/settings.py` - verification + SMTP settings
- `backend/app/core/security/{auth,__init__}.py` - token create/hash helpers
- `backend/app/integrations/email/factory.py` - `smtp` provider
- `backend/app/api/deps.py` - service wiring, `get_verified_user`
- `backend/app/api/auth/router.py` - register sends email; two new endpoints
- `backend/app/api/favorites/router.py`, `backend/app/api/watch/router.py` - `get_current_user` -> `get_verified_user` on account-scoped routes only (authorised). Public `/stream` and `/content` untouched.
- `frontend/src/{types/index.ts,services/api/client.ts,services/api/auth.ts,features/auth/{AuthContext.tsx,context.ts},app/App.tsx,pages/profile/ProfilePage.tsx,pages/anime/AnimeDetailPage.tsx,pages/watch/WatchPage.tsx}`
- `README.md`
- `tests/backend/conftest.py` - **see warning W1**
- `tests/backend/test_public_flow.py` - **see warning W2**

Deleted: none.

## 4. API
- `POST /api/auth/register` - unchanged contract; response adds `email_verified`; sends the email; duplicate still 409.
- `POST /api/auth/verify-email` `{token}` - 200 `{detail}`; 400 generic for unknown/expired/used/inactive; 422 empty or >256 chars; 429 (5/min/IP).
- `POST /api/auth/resend-verification` `{email}` - 202 with one fixed message for every case; 422 bad email; 429 (5/min/IP).
- Gated routes (favorites, watch progress/history) - 401 no token; 403 `{"detail":{"code":"email_not_verified","message":...}}` unverified.

## 5. Security
Token: `secrets.token_urlsafe(32)`; only the SHA-256 is stored; 24 h expiry (UTC);
single-use via conditional UPDATE inside one transaction with a user-row lock;
other outstanding tokens expire on success. No raw token in DB, logs (tested),
or responses. Resend/verify give uniform responses (no enumeration through
these endpoints). Throttling: per IP + per account. The link uses a URL
fragment and the page scrubs it from the address bar.

## 6. Email delivery
`EMAIL_PROVIDER=memory` (default) delivers nothing. `smtp` uses stdlib
`smtplib` with timeout, STARTTLS/SSL and optional login; every failure raises
and is logged by exception type only; registration/resend still return their
normal response and the user can resend. No real SMTP server or real address
was contacted. No outbox/worker added (rationale in the ADR).

## 7. Database
`users.email_verified_at` (nullable tz datetime) + `email_verification_tokens`
(`id`, `user_id` FK -> users indexed, `token_hash` unique, `created_at`,
`expires_at`, `used_at`). Revision `b3d1c8a47e52`, down_revision `6e4b7f9c2a11`
(single head). Backfills existing users as verified. Downgrade drops the table
then the column. MySQL found a real defect in my first downgrade (index needed
by FK); fixed and re-verified.

## 8. Frontend
Register still signs the user in; the Profile page then shows "Verify your
email" (W4: "Your account is awaiting email verification. If you have not received a verification link, you can request another one below.") with a resend button (in-flight guard, 60 s cooldown, 429 handling).
`/verify-email` reads the fragment token, scrubs it, submits once (guarded
against StrictMode double-fire), and shows verifying / success / invalid-or-
expired / incomplete-link / rate-limited states. `refreshUser` was added to
`AuthContext` so a signed-in session picks up verification. Favorites and
watch-progress UI only activate for verified users; unverified users see a hint.

## 9. Finalization summary (W3, W4, W5)
- **W3 - concurrent resend race: FIXED and verified on MySQL.** Cooldown and hourly-cap checks plus the token insert now run in one transaction under a `SELECT ... FOR UPDATE` lock on the user's row.
- **W4 - frontend message: FIXED.** The Profile page no longer claims a link was sent.
- **W5 - timing side-channel: DOCUMENTED** in ADR 0006 as an accepted, unsolved limitation. No behaviour change.
- **W1 (`conftest.py`) and W2 (`test_public_flow.py`): preserved byte-for-byte** (section 14).

## 10. Files changed in this finalization (exact)
| File | Change |
|---|---|
| `backend/app/repositories/email_verification/repository.py` | New `issue_if_allowed` (locked, atomic); removed the now-unused `latest_created_at` / `count_created_since` (no other users, checked by grep) |
| `backend/app/services/email_verification/service.py` | Uses `issue_if_allowed`; sends only after it returns `issued`; removed unused helper/imports |
| `frontend/src/pages/profile/ProfilePage.tsx` | Message text only |
| `docs/decisions/0006-email-verification.md` | Resend-concurrency design (W3), timing side-channel + DATETIME-rounding limitations (W5) |
| `tests/backend/test_email_verification_mysql.py` | +7 MySQL-gated resend/verify concurrency tests, +`email` option on the local `new_user` helper |
| `tests/backend/test_email_verification_endpoints.py` | +2 SQLite functional tests of the new repository method |
| `docs/tasks/TASK_11_FINAL_REPORT.md` | This report (updated in place) |

No migration, no API contract, no settings, and no other frontend file changed.

## 11. Database concurrency strategy (W3)
`issue_if_allowed(user_id, token_hash, ttl, cooldown, cap)`:
1. End any open read transaction (`rollback`) so the lock is the first statement of a fresh transaction.
2. `SELECT is_active, email_verified_at FROM users WHERE id=:id FOR UPDATE` - every resend for one account serialises here; also re-checks active/unverified.
3. Take the timestamp (after the lock), check cooldown, check hourly cap.
4. Insert the token and `commit` (releases the lock). Rejections `rollback`.
5. The service sends the email only after `issued` - no lock is held during SMTP; rejected requests send nothing.

Why step 1 matters: under MySQL REPEATABLE READ the user lookup that precedes a resend pins the snapshot, so without it the post-lock count queries would not see a token committed by the request we waited for. Lock order is user -> token, identical to `consume_and_verify`, so resend and verification cannot deadlock. No new table, no worker; the existing `users` row is the lock. Older links are not invalidated by a resend (unchanged).

## 12. Concurrent resend test methodology
All in `tests/backend/test_email_verification_mysql.py`, gated on `MYSQL_TEST_DATABASE_URL`, refusing any database except `anime_metadata_migration_test`. Each worker thread has its own `Session`/connection; threads are released together by a `Barrier`; they go through the public resend path (user lookup, limits, insert, send) with a thread-safe counting fake sender. They request the existing `real_verification_email` opt-in fixture (conftest unchanged).

- 12 parallel resends, same user -> exactly 1 token, 1 email (cooldown cannot be bypassed).
- Cap isolated (cooldown disabled; 3 aged tokens, 12 parallel) -> exactly 5 tokens total, exactly 2 emails.
- Already at cap (5 aged tokens, 12 parallel) -> 0 new tokens, 0 emails.
- Two users x 8 parallel each -> exactly 1 token and 1 email per user.
- A session holds user A's row lock: resend for B completes while resend for A waits, then completes after release (serialises on the row; others not blocked).
- While `send()` is blocked, another session can take `FOR UPDATE` on that user in < 2 s (no lock during SMTP).
- 4 resend + 4 verify in parallel, same user -> no DB error/deadlock, user verified, no redeemable token left.
- 5 parallel HTTP `POST /resend-verification` through the app (DB overridden to MySQL sessions) -> five 202, 1 token, 1 email.

**Negative control:** before the fix, the six tests whose names contain "resend" were run against the unfixed code on the same MySQL database. Four failed because of the race (12 tokens instead of 1; 15 instead of the cap of 5; 8 instead of 1 for one user; the row-serialisation assertion, since no lock existed). The HTTP test failed for an unrelated reason (my test user's `.test` address was rejected with 422, fixed afterwards), so it was **not** a valid control, and the resend+verify deadlock check passed on both versions as a regression guard. The "no lock during SMTP" test was outside that selection and passes trivially on the unfixed code (no lock existed); it guards against a future regression that holds the lock while sending. SQLite tests are functional only; SQLite ignores `FOR UPDATE` and is not claimed to prove locking.

## 13. Results (executed in this round; MySQL 8.0.46, DB `anime_metadata_migration_test` only)
| Check | Result |
|---|---|
| Negative control: resend tests vs unfixed code | **PASS** for 4 of 6 (race detected); HTTP test not a valid control (test-data bug, fixed later); deadlock check passed on both versions |
| MySQL Task 11 tests after fix | **PASS** 16 passed (8 pre-existing + 8 new) |
| MySQL concurrent resend/verify subset | **PASS** 10 passed |
| Stability: concurrency subset repeated 15x | **PASS** 0 failing runs of 15 |
| `test_email_verification_endpoints.py` (SQLite) | **PASS** 33 |
| `test_email_verification_smtp.py` (fake smtplib) | **PASS** 9 |
| `test_email_verification_migration.py` | **PASS** (included in the 61 below) |
| Email Verification, all 4 files, MySQL on | **PASS** 61 |
| `pytest tests/backend/` without MySQL env | **PASS** 166 passed, 25 skipped (9 T10 + 16 T11 MySQL-gated) |
| `pytest tests/backend/` with MySQL | **PASS** 191 passed, 0 skipped |
| Alembic current / heads (MySQL test DB) | **PASS** `b3d1c8a47e52 (head)` / single head |
| Migrations modified | none (identical to previous state) |
| `ruff check backend/app tests/backend` | 1 pre-existing finding in protected `test_password_reset_token_repository.py` (untouched); all changed files clean |
| Real SMTP delivery | **NOT TESTED** (fake only; no real mail server contacted) |

## 14. Frontend verification
| Check | Result |
|---|---|
| `./node_modules/.bin/tsc -b` | **PASS** (exit 0) |
| `./node_modules/.bin/vite build` | **PASS** |
| `./node_modules/.bin/oxlint` | **PASS** 0 errors, 6 warnings (same count as before) |
| Only `ProfilePage.tsx` changed on the frontend (diffed vs previous state) | **PASS** |
| Auth behaviour (login/register/refresh/logout UI) in a browser or unit tests | **NOT TESTED** - the project has no frontend test runner; only type-check/build/lint evidence |

## 15. W1 / W2 preservation and protected-task regression
| Check | Result |
|---|---|
| W1 `tests/backend/conftest.py` byte-identical to accepted state | **PASS** |
| W2 `tests/backend/test_public_flow.py` byte-identical to accepted state | **PASS** |
| Protected Task 10/12/13 source and test files byte-identical to the ORIGINAL upload (checked by `cmp`) | **PASS** |
| Task 8/9 `-k "auth or refresh or logout or session"` | **PASS** 37 |
| Task 10 `-k password_reset` (incl. 9 MySQL) | **PASS** 49 |
| Task 12 `-k "anime or provider or episode or external or catalog"` | **PASS** 20 |
| Task 13 `-k "watch or local_video or video or stream or public_flow"` | **PASS** 22 |
| Unverified user: login, `/users/me`, refresh, logout, 403 on gated routes | **PASS** (existing endpoint tests, re-run) |
| Secrets: DB password searched for across the project tree | **PASS** not present |

## 16. Remaining limitations, git state, final status
**Limitations**
- Duplicate registration still returns **409** (approved earlier) - the larger enumeration channel.
- Resend response **timing** can still distinguish existing from unknown accounts (synchronous SMTP); documented in ADR 0006, not solved.
- Real SMTP delivery **NOT TESTED**. Registration returns 201 even if the email could not be sent.
- Frontend UI flows have only type-check/build/lint evidence (**NOT TESTED** interactively).
- Per-IP limiter is in-process (ADR 0004).
- MySQL `DATETIME` rounds to whole seconds, so the 60 s cooldown can be ~60.5 s (ADR 0006).

**Git state: NOT VERIFIABLE.** The project has no `.git`, so branch, working-tree status and `git diff --check` were **NOT TESTED**. Substitute run: `git diff --no-index --check` between the previous accepted state and the current tree reported no whitespace errors in backend, tests, docs or frontend (a substitute, not the requested command). Final diff = the 7 files in section 10.

**Final status: COMPLETE WITH WARNINGS.**
Every item on the "COMPLETE only if" list is satisfied: W3 fixed and verified by genuine MySQL concurrency tests (with a negative control), W4 fixed with frontend checks passing, W5 documented, W1/W2 preserved, protected regressions pass, no unresolved critical issue. The "warnings" are only the unverifiable/untested items above (no git repository, no real SMTP, no interactive frontend test).
