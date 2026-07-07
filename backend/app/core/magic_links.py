"""Email magic-link helpers."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode

from app.core.config import settings


def normalize_email(value: str) -> str:
    return value.strip().casefold()


def new_magic_token() -> str:
    return secrets.token_urlsafe(32)


def hash_magic_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_magic_link(token: str) -> str:
    base = settings.magic_link_consume_url
    if not base:
        raise RuntimeError("MAGIC_LINK_CONSUME_URL is not configured")
    return f"{base}?{urlencode({'token': token})}"


def _send_sync(recipient: str, link: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP is not configured")

    message = EmailMessage()
    message["Subject"] = "Вход в Health Compass"
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(
        "Для входа в Health Compass откройте ссылку:\n\n"
        f"{link}\n\n"
        "Ссылка действует 15 минут и может быть использована только один раз."
    )

    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls and not settings.smtp_use_ssl:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


async def send_magic_link(recipient: str, token: str) -> None:
    await asyncio.to_thread(_send_sync, recipient, build_magic_link(token))
