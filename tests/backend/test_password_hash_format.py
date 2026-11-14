# tests/backend/test_password_hash_format.py
from app.core.security.auth import hash_password, verify_password  # yo'lni moslang


def test_hash_password_uses_argon2id():
    hashed = hash_password("Correct-Horse-9!")
    assert hashed.startswith("$argon2id$")
    assert verify_password("Correct-Horse-9!", hashed)