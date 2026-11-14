"""Unit tests for the EmailSender abstraction and its in-memory implementation."""

import pytest
from app.integrations.email import (
    EmailMessage,
    EmailSender,
    InMemoryEmailSender,
    get_email_sender,
    reset_email_sender,
)
from app.integrations.email import factory as email_factory


def _message(n: int = 0) -> EmailMessage:
    return EmailMessage(to=f"user{n}@example.com", subject=f"subject {n}", body=f"body {n}")


def test_in_memory_sender_is_an_email_sender_that_records_messages():
    sender = InMemoryEmailSender()
    assert isinstance(sender, EmailSender)

    sender.send(_message(1))

    assert [m.to for m in sender.outbox] == ["user1@example.com"]


def test_in_memory_outbox_is_bounded():
    sender = InMemoryEmailSender()
    limit = sender.outbox.maxlen

    for n in range(limit + 25):
        sender.send(_message(n))

    assert len(sender.outbox) == limit
    assert sender.outbox[-1].to == f"user{limit + 24}@example.com"  # newest kept


def test_factory_returns_one_shared_instance():
    assert get_email_sender() is get_email_sender()


def test_reset_email_sender_empties_the_shared_outbox():
    get_email_sender().send(_message())
    assert len(get_email_sender().outbox) == 1

    reset_email_sender()

    assert len(get_email_sender().outbox) == 0


def test_an_unknown_email_provider_is_rejected(monkeypatch):
    class FakeSettings:
        email_provider = "carrier-pigeon"
        environment = "development"

    monkeypatch.setattr(email_factory, "get_settings", lambda: FakeSettings())

    # __wrapped__ bypasses the lru_cache so the shared instance is not disturbed.
    with pytest.raises(ValueError, match="Unknown email_provider"):
        get_email_sender.__wrapped__()
