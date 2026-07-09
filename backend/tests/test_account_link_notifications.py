from __future__ import annotations

from app.core import magic_links


async def test_notification_fanout_attempts_every_recipient(monkeypatch) -> None:
    attempted: list[str] = []

    async def fake_send(recipient: str, providers: tuple[str, ...]) -> None:
        attempted.append(recipient)
        assert providers == ("Google", "Email Magic Link")
        if recipient == "broken@example.com":
            raise RuntimeError("mailbox unavailable")

    monkeypatch.setattr(magic_links, "send_account_linked_notification", fake_send)

    failures = await magic_links.send_account_linked_notifications(
        (
            "first@example.com",
            "broken@example.com",
            "last@example.com",
        ),
        ("Google", "Email Magic Link"),
    )

    assert attempted == [
        "first@example.com",
        "broken@example.com",
        "last@example.com",
    ]
    assert failures == ("broken@example.com",)


async def test_notification_fanout_reports_no_failures(monkeypatch) -> None:
    attempted: list[str] = []

    async def fake_send(recipient: str, providers: tuple[str, ...]) -> None:
        attempted.append(recipient)

    monkeypatch.setattr(magic_links, "send_account_linked_notification", fake_send)

    failures = await magic_links.send_account_linked_notifications(
        ("one@example.com", "two@example.com"),
        ("Google", "Email Magic Link"),
    )

    assert attempted == ["one@example.com", "two@example.com"]
    assert failures == ()
