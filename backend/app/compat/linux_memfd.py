"""Linux memfd and file-sealing compatibility for constrained CPython builds.

Some self-contained CPython distributions are compiled with HAVE_MEMFD_CREATE=0
and omit the related ``os``/``fcntl`` attributes even when the running Linux
kernel and libc fully support the same primitives. Health Compass requires the
kernel primitive itself, not the presence of a particular CPython wrapper.

This module never falls back to a filesystem temporary file. It either exposes
the native CPython API, calls libc ``memfd_create`` directly, or fails closed.
"""

from __future__ import annotations

import ctypes
import errno
import fcntl
import os
import sys
from collections.abc import Callable
from typing import Any

# Linux UAPI constants from include/uapi/linux/memfd.h and asm-generic/fcntl.h.
# These values are ABI constants, not kernel-version-dependent feature guesses.
MFD_CLOEXEC = 0x0001
MFD_ALLOW_SEALING = 0x0002

F_ADD_SEALS = 1033
F_GET_SEALS = 1034
F_SEAL_SEAL = 0x0001
F_SEAL_SHRINK = 0x0002
F_SEAL_GROW = 0x0004
F_SEAL_WRITE = 0x0008

READONLY_SEALS = F_SEAL_WRITE | F_SEAL_GROW | F_SEAL_SHRINK | F_SEAL_SEAL

_native_memfd_create: Callable[[str | bytes, int], int] | None = getattr(
    os,
    "memfd_create",
    None,
)


def _load_libc_memfd_create() -> Any | None:
    if sys.platform != "linux":
        return None
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        function = libc.memfd_create
    except (AttributeError, OSError):
        return None
    function.argtypes = [ctypes.c_char_p, ctypes.c_uint]
    function.restype = ctypes.c_int
    return function


_libc_memfd_create = _load_libc_memfd_create()


def memfd_create(name: str | bytes, flags: int = MFD_CLOEXEC) -> int:
    """Create an anonymous Linux memory file or fail closed.

    Prefer CPython's native wrapper when available. Otherwise call the libc
    wrapper for the same kernel primitive. No disk-backed fallback is allowed.
    """

    if _native_memfd_create is not None:
        return _native_memfd_create(name, flags)

    if sys.platform != "linux" or _libc_memfd_create is None:
        raise OSError(errno.ENOSYS, "Linux memfd_create is unavailable")

    encoded_name = name if isinstance(name, bytes) else os.fsencode(name)
    if b"\x00" in encoded_name:
        raise ValueError("memfd name must not contain NUL bytes")

    ctypes.set_errno(0)
    descriptor = int(_libc_memfd_create(encoded_name, flags))
    if descriptor < 0:
        error_number = ctypes.get_errno() or errno.EIO
        raise OSError(error_number, os.strerror(error_number))
    return descriptor


def add_seals(descriptor: int, seals: int = READONLY_SEALS) -> None:
    """Apply Linux file seals to a memfd descriptor."""

    fcntl.fcntl(descriptor, F_ADD_SEALS, seals)


def get_seals(descriptor: int) -> int:
    """Return the active Linux file seals for a memfd descriptor."""

    return int(fcntl.fcntl(descriptor, F_GET_SEALS))


def install_linux_memfd_compat() -> bool:
    """Expose missing CPython wrappers when the Linux primitive is usable.

    The application and existing tests historically call ``os.memfd_create``
    and ``fcntl.F_*`` directly. Installing only missing attributes keeps native
    CPython behavior unchanged while normalizing constrained manylinux builds.
    """

    if sys.platform != "linux":
        return False
    if _native_memfd_create is None and _libc_memfd_create is None:
        return False

    if not hasattr(os, "memfd_create"):
        setattr(os, "memfd_create", memfd_create)
    if not hasattr(os, "MFD_CLOEXEC"):
        setattr(os, "MFD_CLOEXEC", MFD_CLOEXEC)
    if not hasattr(os, "MFD_ALLOW_SEALING"):
        setattr(os, "MFD_ALLOW_SEALING", MFD_ALLOW_SEALING)

    for name, value in (
        ("F_ADD_SEALS", F_ADD_SEALS),
        ("F_GET_SEALS", F_GET_SEALS),
        ("F_SEAL_SEAL", F_SEAL_SEAL),
        ("F_SEAL_SHRINK", F_SEAL_SHRINK),
        ("F_SEAL_GROW", F_SEAL_GROW),
        ("F_SEAL_WRITE", F_SEAL_WRITE),
    ):
        if not hasattr(fcntl, name):
            setattr(fcntl, name, value)

    return all(
        (
            hasattr(os, "memfd_create"),
            hasattr(os, "MFD_CLOEXEC"),
            hasattr(os, "MFD_ALLOW_SEALING"),
            hasattr(fcntl, "F_ADD_SEALS"),
            hasattr(fcntl, "F_GET_SEALS"),
            hasattr(fcntl, "F_SEAL_WRITE"),
        )
    )
