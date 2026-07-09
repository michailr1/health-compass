from __future__ import annotations

import uuid

import pytest

from app.api.routes.sign_in_methods import build_settings_link_plan
from app.models.user import UserIdentity


def identity(provider: str, subject: str, claims: dict) -> UserIdentity:
    return UserIdentity(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider=provider,
        subject=subject,
        issuer="issuer",
        claims=claims,
    )


def test_add_google_uses_verified_email_identity_as_source() -> None:
    source = identity(
        "email",
        "User@Example.com ",
        {"email": "User@Example.com", "email_verified": True},
    )

    plan = build_settings_link_plan("google", {"email": source})

    assert plan is not None
    assert plan.source is source
    assert plan.flow_type == "settings_add_google"
    assert plan.normalized_email == "user@example.com"


def test_add_email_uses_verified_google_identity_as_source() -> None:
    source = identity(
        "google",
        "opaque-google-sub",
        {"email": "User@Example.com ", "email_verified": True},
    )

    plan = build_settings_link_plan("email", {"google": source})

    assert plan is not None
    assert plan.source is source
    assert plan.flow_type == "settings_add_email"
    assert plan.normalized_email == "user@example.com"


def test_already_connected_provider_returns_no_plan() -> None:
    source = identity("google", "sub", {"email_verified": True, "email": "user@example.com"})

    assert build_settings_link_plan("google", {"google": source}) is None


@pytest.mark.parametrize(
    ("provider", "identities", "message"),
    [
        ("google", {}, "verified Email Magic Link"),
        (
            "google",
            {"email": identity("email", "user@example.com", {"email_verified": False})},
            "verified Email Magic Link",
        ),
        ("email", {}, "verified Google identity"),
        (
            "email",
            {"google": identity("google", "sub", {"email_verified": False})},
            "verified Google identity",
        ),
        (
            "email",
            {"google": identity("google", "sub", {"email_verified": True, "email": ""})},
            "Google email is unavailable",
        ),
    ],
)
def test_invalid_settings_link_sources_are_rejected(
    provider: str,
    identities: dict[str, UserIdentity],
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        build_settings_link_plan(provider, identities)
