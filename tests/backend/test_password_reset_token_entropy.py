from app.core.security import create_password_reset_token


def test_reset_tokens_are_unique_and_long_enough():
    tokens = {create_password_reset_token() for _ in range(1000)}
    assert len(tokens) == 1000
    assert all(len(token) >= 43 for token in tokens)