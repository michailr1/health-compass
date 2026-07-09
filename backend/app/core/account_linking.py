"""Cryptographic helpers for pre-bootstrap account-linking flows."""

from __future__ import annotations

import hashlib
import secrets


def new_browser_binding() -> str:
    """Return a high-entropy browser binding stored only in an HttpOnly cookie."""
    return secrets.token_urlsafe(32)


def hash_secret(value: str) -> str:
    """Hash an opaque browser/state/token value before database persistence."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def constant_time_hash_match(raw_value: str, expected_hash: str) -> bool:
    """Compare a raw secret with a stored SHA-256 digest in constant time."""
    return secrets.compare_digest(hash_secret(raw_value), expected_hash)
