"""Regression tests for Linux memfd compatibility on constrained CPython builds."""

from __future__ import annotations

import fcntl
import os

import pytest

from app.compat import linux_memfd


def test_stdlib_memfd_surface_is_available_after_app_import() -> None:
    assert hasattr(os, "memfd_create")
    assert hasattr(os, "MFD_CLOEXEC")
    assert hasattr(os, "MFD_ALLOW_SEALING")
    assert hasattr(fcntl, "F_ADD_SEALS")
    assert hasattr(fcntl, "F_GET_SEALS")
    assert hasattr(fcntl, "F_SEAL_WRITE")


def test_libc_fallback_creates_and_seals_memfd(monkeypatch: pytest.MonkeyPatch) -> None:
    assert linux_memfd._libc_memfd_create is not None
    monkeypatch.setattr(linux_memfd, "_native_memfd_create", None)

    descriptor = linux_memfd.memfd_create(
        "hc-libc-fallback-test",
        linux_memfd.MFD_CLOEXEC | linux_memfd.MFD_ALLOW_SEALING,
    )
    try:
        os.write(descriptor, b"verified")
        linux_memfd.add_seals(descriptor)
        assert linux_memfd.get_seals(descriptor) == linux_memfd.READONLY_SEALS
        with pytest.raises(OSError):
            os.write(descriptor, b"x")
    finally:
        os.close(descriptor)


def test_memfd_name_rejects_nul_in_libc_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    assert linux_memfd._libc_memfd_create is not None
    monkeypatch.setattr(linux_memfd, "_native_memfd_create", None)

    with pytest.raises(ValueError, match="NUL"):
        linux_memfd.memfd_create(b"invalid\x00name")
