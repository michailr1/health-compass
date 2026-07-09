from __future__ import annotations

from app.core.account_linking import (
    constant_time_hash_match,
    hash_secret,
    new_browser_binding,
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
