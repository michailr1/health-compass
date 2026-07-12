"""Regression tests for Linux memfd compatibility on constrained CPython builds."""

from __future__ import annotations

import fcntl
import os

import pytest

from app.compat import linux_memfd


def test_installer_restores_missing_cpython_memfd_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ("memfd_create", "MFD_CLOEXEC", "MFD_ALLOW_SEALING"):
        monkeypatch.delattr(os, name, raising=False)
    for name in (
        "F_ADD_SEALS",
        "F_GET_SEALS",
        "F_SEAL_SEAL",
        "F_SEAL_SHRINK",
        "F_SEAL_GROW",
        "F_SEAL_WRITE",
    ):
        monkeypatch.delattr(fcntl, name, raising=False)

    assert linux_memfd.install_linux_memfd_compat() is True
    assert hasattr(os, "memfd_create")
    assert getattr(os, "MFD_CLOEXEC") == linux_memfd.MFD_CLOEXEC
    assert getattr(os, "MFD_ALLOW_SEALING") == linux_memfd.MFD_ALLOW_SEALING
    assert getattr(fcntl, "F_ADD_SEALS") == linux_memfd.F_ADD_SEALS
    assert getattr(fcntl, "F_GET_SEALS") == linux_memfd.F_GET_SEALS
    assert getattr(fcntl, "F_SEAL_WRITE") == linux_memfd.F_SEAL_WRITE


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
