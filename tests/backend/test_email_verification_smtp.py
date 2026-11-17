"""
SmtpEmailSender unit tests (Task 11). smtplib is replaced by a fake: these
verify OUR behaviour (headers, TLS/login sequence, failures propagate) but do
NOT prove delivery through a real mail server.
"""

import smtplib

import pytest
from app.core.config import get_settings
from app.integrations.email import EmailMessage, factory
from app.integrations.email.smtp_sender import SmtpEmailSender

MSG = EmailMessage(to="to@example.com", subject="Subject", body="Body with link")


class FakeSMTP:
    instances: list["FakeSMTP"] = []
    fail_on: str | None = None
    refused: dict = {}

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.timeout = host, port, timeout
        self.context = context
        self.calls: list[str] = []
        self.sent = None
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self, context=None):
        self.tls_context = context
        self._step("starttls")

    def login(self, user, password):
        self._step("login")
        self.creds = (user, password)

    def send_message(self, mime):
        self._step("send")
        self.sent = mime
        return FakeSMTP.refused

    def _step(self, name):
        self.calls.append(name)
        if FakeSMTP.fail_on == name:
            raise {
                "starttls": smtplib.SMTPException("tls"),
                "login": smtplib.SMTPAuthenticationError(535, b"bad creds"),
                "send": smtplib.SMTPServerDisconnected("gone"),
            }[name]


@pytest.fixture(autouse=True)
def fake_smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail_on, FakeSMTP.refused = [], None, {}
    monkeypatch.setattr(smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(smtplib, "SMTP_SSL", FakeSMTP)


def _sender(**kw):
    base = dict(
        host="smtp.test", port=587, username="u", password="p",
        from_address="noreply@example.com", from_name="Anime Platform",
    )
    base.update(kw)
    return SmtpEmailSender(**base)


def test_success_sequence_and_headers():
    _sender().send(MSG)
    smtp = FakeSMTP.instances[0]
    assert smtp.calls == ["starttls", "login", "send"]
    assert smtp.timeout == 10.0
    assert smtp.sent["To"] == "to@example.com"
    assert "noreply@example.com" in smtp.sent["From"]
    assert smtp.sent["Subject"] == "Subject"
    assert "Body with link" in smtp.sent.get_content()


def test_no_login_without_username_and_no_starttls_when_disabled():
    _sender(username="", use_tls=False).send(MSG)
    assert FakeSMTP.instances[0].calls == ["send"]


@pytest.mark.parametrize("step,exc", [
    ("starttls", smtplib.SMTPException),
    ("login", smtplib.SMTPAuthenticationError),
    ("send", smtplib.SMTPServerDisconnected),
])
def test_failures_propagate_so_delivery_is_never_claimed(step, exc):
    FakeSMTP.fail_on = step
    with pytest.raises(exc):
        _sender().send(MSG)


def test_refused_recipient_raises():
    FakeSMTP.refused = {"to@example.com": (550, b"no such user")}
    with pytest.raises(smtplib.SMTPRecipientsRefused):
        _sender().send(MSG)


def test_connection_timeout_propagates(monkeypatch):
    def timeout(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(smtplib, "SMTP", timeout)
    with pytest.raises(TimeoutError):
        _sender().send(MSG)


def test_requires_host_and_sender_address():
    with pytest.raises(ValueError):
        _sender(host="")
    with pytest.raises(ValueError):
        _sender(from_address="")


def test_factory_builds_smtp_sender_from_settings(monkeypatch):
    monkeypatch.setenv("EMAIL_PROVIDER", "smtp")
    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("EMAIL_FROM_ADDRESS", "noreply@example.com")
    get_settings.cache_clear()
    factory.get_email_sender.cache_clear()
    try:
        assert isinstance(factory.get_email_sender(), SmtpEmailSender)
    finally:
        monkeypatch.undo()
        get_settings.cache_clear()
        factory.get_email_sender.cache_clear()
