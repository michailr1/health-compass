from __future__ import annotations

import datetime
import uuid

from app.api.routes.identity import build_sign_in_method_responses
from app.models.user import UserIdentity


def identity(
    *,
    provider: str,
    subject: str,
    claims: dict,
    created_at: datetime.datetime,
) -> UserIdentity:
    return UserIdentity(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        provider=provider,
        subject=subject,
        issuer="issuer",
        claims=claims,
        created_at=created_at,
        last_seen_at=None,
    )


def test_single_identity_cannot_be_removed() -> None:
    created_at = datetime.datetime(2026, 7, 9, tzinfo=datetime.UTC)
    responses = build_sign_in_method_responses(
        [
            identity(
                provider="google",
                subject="opaque-google-subject",
                claims={"email": "user@example.com", "email_verified": True},
                created_at=created_at,
            )
        ]
    )

    assert len(responses) == 1
    assert responses[0].provider == "google"
    assert responses[0].label == "user@example.com"
    assert responses[0].verified is True
    assert responses[0].can_remove is False
    assert "opaque-google-subject" not in responses[0].model_dump_json()


def test_two_identities_are_presented_as_removable() -> None:
    created_at = datetime.datetime(2026, 7, 9, tzinfo=datetime.UTC)
    responses = build_sign_in_method_responses(
        [
            identity(
                provider="google",
                subject="google-sub",
                claims={"email": "user@example.com", "email_verified": True},
                created_at=created_at,
            ),
            identity(
                provider="email",
                subject="user@example.com",
                claims={"email": "user@example.com", "email_verified": True},
                created_at=created_at,
            ),
        ]
    )

    assert [item.provider for item in responses] == ["google", "email"]
    assert all(item.can_remove for item in responses)
    assert all(item.verified for item in responses)


def test_unknown_provider_does_not_expose_subject() -> None:
    created_at = datetime.datetime(2026, 7, 9, tzinfo=datetime.UTC)
    response = build_sign_in_method_responses(
        [
            identity(
                provider="future-provider",
                subject="private-provider-subject",
                claims={},
                created_at=created_at,
            )
        ]
    )[0]

    assert response.label == "future-provider"
    assert response.verified is False
    assert "private-provider-subject" not in response.model_dump_json()
