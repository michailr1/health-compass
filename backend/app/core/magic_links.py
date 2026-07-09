"""Email magic-link and account-security notification helpers."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode, urlsplit, urlunsplit

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


def build_link_email_url(token: str) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/auth/link/email/consume", urlencode({"token": token}), ""))


def build_identity_removal_email_url(token: str) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/auth/identities/remove/email/consume", urlencode({"token": token}), ""))


def build_duplicate_resolution_email_url(token: str) -> str:
    parts = urlsplit(settings.frontend_url)
    return urlunsplit((parts.scheme, parts.netloc, "/api/auth/duplicates/email/consume", urlencode({"token": token}), ""))


def _send_sync(recipient: str, subject: str, body: str) -> None:
    if not settings.smtp_host or not settings.smtp_from_email:
        raise RuntimeError("SMTP is not configured")
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = settings.smtp_from_email
    message["To"] = recipient
    message.set_content(body)
    smtp_class = smtplib.SMTP_SSL if settings.smtp_use_ssl else smtplib.SMTP
    with smtp_class(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
        if settings.smtp_starttls and not settings.smtp_use_ssl:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


async def send_magic_link(recipient: str, token: str) -> None:
    link = build_magic_link(token)
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Вход в Health Compass",
        "Для входа в Health Compass откройте ссылку:\n\n"
        f"{link}\n\n"
        "Ссылка действует 15 минут и может быть использована только один раз.",
    )


async def send_account_link_email(recipient: str, token: str) -> None:
    link = build_link_email_url(token)
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Подтверждение способа входа Health Compass",
        "Вы начали связывание входа через Google с существующим профилем Health Compass.\n\n"
        "Для подтверждения владения email откройте специальную ссылку:\n\n"
        f"{link}\n\n"
        "Эта ссылка имеет назначение link_email, действует ограниченное время и не может использоваться для обычного входа. "
        "Если вы не начинали связывание, проигнорируйте письмо.",
    )


async def send_identity_removal_email(recipient: str, token: str, target_provider: str) -> None:
    link = build_identity_removal_email_url(token)
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Подтверждение отключения способа входа Health Compass",
        f"Запрошено отключение способа входа: {target_provider}.\n\n"
        "Для подтверждения через оставшийся Email Magic Link откройте ссылку:\n\n"
        f"{link}\n\n"
        "Ссылка имеет отдельное назначение remove_identity_email, действует ограниченное время "
        "и не может использоваться для обычного входа или связывания аккаунтов. "
        "Если вы не запрашивали отключение, проигнорируйте письмо.",
    )


async def send_duplicate_resolution_email(recipient: str, token: str) -> None:
    link = build_duplicate_resolution_email_url(token)
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Подтверждение объединения пустого дубликата Health Compass",
        "Найдены два аккаунта Health Compass с одним подтверждённым email. Один из них пуст и может быть безопасно поглощён.\n\n"
        "Чтобы доказать владение вторым аккаунтом, откройте специальную ссылку:\n\n"
        f"{link}\n\n"
        "Ссылка имеет отдельное назначение resolve_duplicate_email. Она не подходит для обычного входа, "
        "связывания способов входа или удаления identity. Если вы не запускали эту процедуру, проигнорируйте письмо.",
    )


async def send_identity_removed_notification(recipient: str, removed_provider: str) -> None:
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Способ входа Health Compass отключён",
        f"Из вашего аккаунта Health Compass отключён способ входа: {removed_provider}.\n\n"
        "Оставшийся способ входа продолжает открывать тот же профиль. Если вы не выполняли это действие, "
        "завершите активные сессии и обратитесь в поддержку.",
    )


async def send_account_linked_notification(recipient: str, providers: tuple[str, ...]) -> None:
    provider_text = " и ".join(providers)
    await asyncio.to_thread(
        _send_sync,
        recipient,
        "Способы входа Health Compass связаны",
        "В вашем аккаунте Health Compass успешно связаны способы входа: "
        f"{provider_text}.\n\n"
        "Теперь они открывают один и тот же профиль. Если вы не выполняли это действие, "
        "завершите активные сессии и обратитесь в поддержку.",
    )


async def send_account_linked_notifications(
    recipients: tuple[str, ...],
    providers: tuple[str, ...],
) -> tuple[str, ...]:
    failures: list[str] = []
    for recipient in recipients:
        try:
            await send_account_linked_notification(recipient, providers)
        except Exception:
            failures.append(recipient)
    return tuple(failures)
