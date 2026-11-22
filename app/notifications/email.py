from __future__ import annotations

import smtplib
from email.message import EmailMessage

from app.config import settings
from app.logging import get_logger

log = get_logger(__name__)


class EmailNotConfiguredError(Exception):
    """Raised when sending is attempted but no SMTP relay is configured - an expected condition
    for anyone running contxt without having set CONTXT_SMTP_* yet, not a bug."""


def send_notification_email(to_address: str, subject: str, body: str) -> None:
    if not settings.smtp_host:
        raise EmailNotConfiguredError("CONTXT_SMTP_HOST is not set - no email relay configured")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_address or settings.smtp_username
    message["To"] = to_address
    message.set_content(body)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as smtp:
        smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password)
        smtp.send_message(message)
    log.info("sent notification email to %s", to_address)
