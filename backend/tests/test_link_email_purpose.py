from __future__ import annotations

from app.core import magic_links


def test_login_and_link_email_urls_use_distinct_endpoints(monkeypatch) -> None:
    monkeypatch.setattr(
        magic_links.settings,
        "magic_link_consume_url",
        "https://health.example/api/auth/email/consume",
    )
    monkeypatch.setattr(
        magic_links.settings,
        "frontend_url",
        "https://health.example/app",
    )

    login_url = magic_links.build_magic_link("token-value")
    link_url = magic_links.build_link_email_url("token-value")

    assert "/api/auth/email/consume" in login_url
    assert "/api/auth/link/email/consume" in link_url
    assert login_url != link_url
    assert "token=token-value" in login_url
    assert "token=token-value" in link_url
