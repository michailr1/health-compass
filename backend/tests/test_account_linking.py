from __future__ import annotations

from app.core.account_linking import (
    constant_time_hash_match,
    hash_secret,
    new_browser_binding,
)
from app.services.account_linking import (
    NotificationIdentity,
    collect_verified_notification_emails,
)


def test_browser_binding_has_sufficient_entropy_and_is_unique() -> None:
    first = new_browser_binding()
    second = new_browser_binding()

    assert len(first) >= 32
    assert len(second) >= 32
    assert first != second


def test_hash_secret_is_deterministic_and_not_plaintext() -> None:
    value = "opaque-browser-binding"

    digest = hash_secret(value)

    assert digest == hash_secret(value)
    assert digest != value
    assert len(digest) == 64


def test_constant_time_hash_match_accepts_only_original_value() -> None:
    expected_hash = hash_secret("correct-value")

    assert constant_time_hash_match("correct-value", expected_hash) is True
    assert constant_time_hash_match("wrong-value", expected_hash) is False


def test_verified_notification_emails_include_all_unique_verified_addresses() -> None:
    recipients = collect_verified_notification_emails(
        "Canonical@Example.com ",
        [
            NotificationIdentity(
                provider="google",
                subject="google-sub",
                claims={"email": "Google@Example.com", "email_verified": True},
            ),
            NotificationIdentity(
                provider="email",
                subject="email@example.com",
                claims={"email_verified": True},
            ),
            NotificationIdentity(
                provider="email",
                subject="UNVERIFIED@example.com",
                claims={"email_verified": False},
            ),
            NotificationIdentity(
                provider="google",
                subject="duplicate-sub",
                claims={"email": "canonical@example.com", "email_verified": True},
            ),
        ],
    )

    assert recipients == (
        "canonical@example.com",
        "email@example.com",
        "google@example.com",
    )


def test_verified_notification_emails_ignore_empty_and_unverified_claims() -> None:
    recipients = collect_verified_notification_emails(
        "owner@example.com",
        [
            NotificationIdentity(provider="google", subject="sub", claims={}),
            NotificationIdentity(
                provider="google",
                subject="sub-2",
                claims={"email": "", "email_verified": True},
            ),
        ],
    )

    assert recipients == ("owner@example.com",)
