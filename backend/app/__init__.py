"""Health Compass backend package initialization."""

from app.compat.linux_memfd import install_linux_memfd_compat

install_linux_memfd_compat()
