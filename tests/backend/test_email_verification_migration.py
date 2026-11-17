"""
Alembic migration test for Task 11 against a throwaway SQLite FILE (never the
project's dev DB). MySQL migration is verified separately by
test_email_verification_mysql.py (gated).
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND = Path(__file__).resolve().parents[2] / "backend"
PREV, HEAD = "6e4b7f9c2a11", "b3d1c8a47e52"


def _alembic(db_url, *args):
    env = {**os.environ, "DATABASE_URL": db_url, "PYTHONPATH": str(BACKEND)}
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.fixture()
def db_url(tmp_path):
    return f"sqlite:///{tmp_path / 'mig.db'}"


def test_upgrade_backfills_existing_users_and_creates_token_table(db_url):
    assert _alembic(db_url, "upgrade", PREV).returncode == 0
    eng = create_engine(db_url)
    with eng.begin() as c:
        c.execute(text(
            "INSERT INTO users (id,email,hashed_password,is_active,created_at) "
            "VALUES ('u1','old@example.com','h',1,'2026-01-02 03:04:05')"
        ))
    r = _alembic(db_url, "upgrade", "head")
    assert r.returncode == 0, r.stderr
    insp = inspect(eng)
    assert "email_verified_at" in {c["name"] for c in insp.get_columns("users")}
    cols = {c["name"]: c for c in insp.get_columns("email_verification_tokens")}
    assert set(cols) == {"id", "user_id", "token_hash", "created_at", "expires_at", "used_at"}
    idx = {i["name"]: i for i in insp.get_indexes("email_verification_tokens")}
    assert idx["ix_email_verification_tokens_token_hash"]["unique"]
    assert "ix_email_verification_tokens_user_id" in idx
    assert insp.get_foreign_keys("email_verification_tokens")[0]["referred_table"] == "users"
    with eng.connect() as c:
        row = c.execute(text("SELECT email_verified_at, created_at FROM users")).one()
    assert row[0] is not None and row[0] == row[1]  # existing user NOT locked out
    assert _alembic(db_url, "current").stdout.strip().startswith(HEAD)


def test_downgrade_then_upgrade_is_reversible_and_keeps_users(db_url):
    assert _alembic(db_url, "upgrade", "head").returncode == 0
    eng = create_engine(db_url)
    with eng.begin() as c:
        c.execute(text(
            "INSERT INTO users (id,email,hashed_password,is_active,created_at,email_verified_at) "
            "VALUES ('u1','a@example.com','h',1,'2026-01-02 03:04:05',NULL)"
        ))
    assert _alembic(db_url, "downgrade", PREV).returncode == 0
    insp = inspect(eng)
    assert "email_verification_tokens" not in insp.get_table_names()
    assert "email_verified_at" not in {c["name"] for c in insp.get_columns("users")}
    with eng.connect() as c:
        assert c.execute(text("SELECT count(*) FROM users")).scalar() == 1
    assert _alembic(db_url, "upgrade", "head").returncode == 0


def test_single_head():
    out = _alembic("sqlite://", "heads").stdout
    assert out.strip().splitlines() == [f"{HEAD} (head)"]
