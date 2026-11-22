from __future__ import annotations

import smtplib
from types import TracebackType

import pytest

from app.config import settings
from app.notifications.email import EmailNotConfiguredError, send_notification_email


class _FakeSMTP:
    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.calls: list[str] = []

    def __enter__(self) -> _FakeSMTP:
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None
    ) -> None:
        return None

    def starttls(self) -> None:
        self.calls.append("starttls")

    def login(self, username: str, password: str) -> None:
        self.calls.append(f"login:{username}")

    def send_message(self, message: object) -> None:
        self.calls.append("send_message")


def test__send_notification_email_raises_when_not_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "")

    with pytest.raises(EmailNotConfiguredError):
        send_notification_email("alice@example.com", "subject", "body")


def test__send_notification_email_sends_via_smtp_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_port", 587)
    monkeypatch.setattr(settings, "smtp_username", "bot@example.com")
    monkeypatch.setattr(settings, "smtp_password", "secret")
    monkeypatch.setattr(settings, "smtp_from_address", "bot@example.com")

    created: list[_FakeSMTP] = []

    def fake_smtp(host: str, port: int, timeout: int) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout)
        created.append(instance)
        return instance

    monkeypatch.setattr(smtplib, "SMTP", fake_smtp)

    send_notification_email("alice@example.com", "subject", "body")

    assert created[0].host == "smtp.example.com"
    assert created[0].calls == ["starttls", "login:bot@example.com", "send_message"]


def test__send_notification_email_skips_login_without_username(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "smtp_host", "smtp.example.com")
    monkeypatch.setattr(settings, "smtp_username", "")

    created: list[_FakeSMTP] = []

    def fake_smtp(host: str, port: int, timeout: int) -> _FakeSMTP:
        instance = _FakeSMTP(host, port, timeout)
        created.append(instance)
        return instance

    monkeypatch.setattr(smtplib, "SMTP", fake_smtp)

    send_notification_email("alice@example.com", "subject", "body")

    assert created[0].calls == ["starttls", "send_message"]
