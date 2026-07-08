from __future__ import annotations

import base64
import hashlib

import pytest

from app.core import oidc


def test_code_challenge_uses_s256() -> None:
    verifier = "known-verifier"
    expected = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode("ascii")).digest()
    ).rstrip(b"=").decode("ascii")

    assert oidc.code_challenge(verifier) == expected


def test_build_authorization_url_rejects_non_https_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(oidc.settings, "oidc_client_id", "client-id")

    with pytest.raises(ValueError, match="authorization_endpoint"):
        oidc.build_authorization_url(
            {"authorization_endpoint": "http://accounts.example/authorize"},
            "https://app.example/callback",
            "state",
            "nonce",
            "verifier",
        )


def test_build_authorization_url_contains_security_parameters(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(oidc.settings, "oidc_client_id", "client-id")

    url = oidc.build_authorization_url(
        {"authorization_endpoint": "https://accounts.example/authorize"},
        "https://app.example/callback",
        "state-value",
        "nonce-value",
        "verifier-value",
    )

    assert "response_type=code" in url
    assert "state=state-value" in url
    assert "nonce=nonce-value" in url
    assert "code_challenge_method=S256" in url
    assert "scope=openid+email+profile" in url
