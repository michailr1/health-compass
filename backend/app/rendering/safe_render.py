"""Bounded subprocess renderer for verified PDF and image documents."""

from __future__ import annotations

import fcntl
import os
import resource
import signal
import struct
import subprocess
import zlib
from dataclasses import dataclass

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_ALLOWED_PNG_CHUNKS = {
    b"IHDR",
    b"PLTE",
    b"IDAT",
    b"IEND",
    b"tRNS",
    b"sRGB",
    b"gAMA",
    b"cHRM",
    b"pHYs",
    b"bKGD",
}


class SafeRenderError(Exception):
    """Base class for content-free rendering failures."""


class RenderTimeoutError(SafeRenderError):
    pass


class RenderProcessError(SafeRenderError):
    pass


class InvalidRenderedImageError(SafeRenderError):
    pass


class UnsupportedDocumentError(SafeRenderError):
    pass


@dataclass(frozen=True)
class RenderLimits:
    timeout_seconds: int
    cpu_seconds: int
    memory_bytes: int
    max_output_bytes: int
    max_pixels: int
    max_pages: int
    dpi: int


@dataclass(frozen=True)
class PdfInspection:
    page_count: int
    encrypted: bool


@dataclass(frozen=True)
class RenderedPage:
    descriptor: int
    width: int
    height: int


class SafeDocumentRenderer:
    """Run fixed parser/rasterizer commands under strict resource limits."""

    def __init__(
        self,
        *,
        pdfinfo_path: str,
        pdftocairo_path: str,
        magick_path: str,
        limits: RenderLimits,
    ) -> None:
        self.pdfinfo_path = pdfinfo_path
        self.pdftocairo_path = pdftocairo_path
        self.magick_path = magick_path
        self.limits = limits

    def _resource_limiter(self, output_limit: int):
        cpu_seconds = self.limits.cpu_seconds
        memory_bytes = self.limits.memory_bytes

        def apply_limits() -> None:
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            resource.setrlimit(resource.RLIMIT_FSIZE, (output_limit, output_limit))
            resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
            if hasattr(resource, "RLIMIT_NPROC"):
                resource.setrlimit(resource.RLIMIT_NPROC, (16, 16))
            os.umask(0o077)

        return apply_limits

    @staticmethod
    def _new_memfd(name: str) -> int:
        if not hasattr(os, "memfd_create"):
            raise RenderProcessError("Anonymous memory files are unavailable")
        return os.memfd_create(name, getattr(os, "MFD_CLOEXEC", 0))

    @staticmethod
    def _seal_readonly(descriptor: int) -> None:
        if not hasattr(fcntl, "F_ADD_SEALS"):
            raise RenderProcessError("Memory-file sealing is unavailable")
        seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)

    def _run_to_memfd(
        self,
        arguments: list[str],
        *,
        input_descriptor: int,
        output_limit: int,
    ) -> int:
        output_descriptor = self._new_memfd("hc-render-output")
        error_descriptor = self._new_memfd("hc-render-error")
        output_handle = os.fdopen(os.dup(output_descriptor), "wb", closefd=True)
        error_handle = os.fdopen(os.dup(error_descriptor), "wb", closefd=True)
        process: subprocess.Popen[bytes] | None = None
        try:
            process = subprocess.Popen(
                arguments,
                stdin=subprocess.DEVNULL,
                stdout=output_handle,
                stderr=error_handle,
                close_fds=True,
                pass_fds=(input_descriptor,),
                start_new_session=True,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                preexec_fn=self._resource_limiter(output_limit),
            )
            try:
                return_code = process.wait(timeout=self.limits.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise RenderTimeoutError("Document renderer exceeded its timeout") from exc
            finally:
                output_handle.close()
                error_handle.close()

            if return_code != 0:
                raise RenderProcessError("Document renderer rejected the input")
            size = os.fstat(output_descriptor).st_size
            if size < 1 or size > output_limit:
                raise RenderProcessError("Document renderer output is outside limits")
            os.lseek(output_descriptor, 0, os.SEEK_SET)
            return output_descriptor
        except Exception:
            os.close(output_descriptor)
            raise
        finally:
            try:
                error_handle.close()
            except Exception:
                pass
            os.close(error_descriptor)

    @staticmethod
    def _read_bounded_text(descriptor: int, max_bytes: int) -> str:
        size = os.fstat(descriptor).st_size
        if size < 1 or size > max_bytes:
            raise RenderProcessError("Parser metadata output is outside limits")
        os.lseek(descriptor, 0, os.SEEK_SET)
        payload = os.read(descriptor, size)
        try:
            return payload.decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise RenderProcessError("Parser metadata output is invalid") from exc

    def inspect_pdf(self, verified_descriptor: int) -> PdfInspection:
        input_path = f"/proc/self/fd/{verified_descriptor}"
        descriptor = self._run_to_memfd(
            [self.pdfinfo_path, "-enc", "UTF-8", input_path],
            input_descriptor=verified_descriptor,
            output_limit=64 * 1024,
        )
        try:
            payload = self._read_bounded_text(descriptor, 64 * 1024)
        finally:
            os.close(descriptor)

        fields: dict[str, str] = {}
        for line in payload.splitlines():
            if ":" not in line:
                continue
            key, value = line.split(":", 1)
            fields[key.strip().lower()] = value.strip()
        try:
            page_count = int(fields["pages"])
        except (KeyError, ValueError) as exc:
            raise RenderProcessError("PDF page count is unavailable") from exc
        encrypted = fields.get("encrypted", "no").lower() != "no"
        if page_count < 1 or page_count > self.limits.max_pages:
            raise UnsupportedDocumentError("PDF page count is outside limits")
        if encrypted:
            raise UnsupportedDocumentError("Password-protected PDF is not supported")
        return PdfInspection(page_count=page_count, encrypted=False)

    def render_pdf_page(self, verified_descriptor: int, page_number: int) -> RenderedPage:
        if page_number < 1 or page_number > self.limits.max_pages:
            raise UnsupportedDocumentError("PDF page number is outside limits")
        input_path = f"/proc/self/fd/{verified_descriptor}"
        descriptor = self._run_to_memfd(
            [
                self.pdftocairo_path,
                "-png",
                "-singlefile",
                "-f",
                str(page_number),
                "-l",
                str(page_number),
                "-r",
                str(self.limits.dpi),
                input_path,
                "-",
            ],
            input_descriptor=verified_descriptor,
            output_limit=self.limits.max_output_bytes,
        )
        try:
            width, height = validate_png_descriptor(
                descriptor,
                max_bytes=self.limits.max_output_bytes,
                max_pixels=self.limits.max_pixels,
            )
            self._seal_readonly(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            return RenderedPage(descriptor=descriptor, width=width, height=height)
        except Exception:
            os.close(descriptor)
            raise

    def render_image(self, verified_descriptor: int) -> RenderedPage:
        input_path = f"/proc/self/fd/{verified_descriptor}"
        descriptor = self._run_to_memfd(
            [
                self.magick_path,
                input_path,
                "-auto-orient",
                "-strip",
                "-colorspace",
                "sRGB",
                "png:-",
            ],
            input_descriptor=verified_descriptor,
            output_limit=self.limits.max_output_bytes,
        )
        try:
            width, height = validate_png_descriptor(
                descriptor,
                max_bytes=self.limits.max_output_bytes,
                max_pixels=self.limits.max_pixels,
            )
            self._seal_readonly(descriptor)
            os.lseek(descriptor, 0, os.SEEK_SET)
            return RenderedPage(descriptor=descriptor, width=width, height=height)
        except Exception:
            os.close(descriptor)
            raise


def _read_exact(descriptor: int, count: int) -> bytes:
    data = bytearray()
    while len(data) < count:
        chunk = os.read(descriptor, count - len(data))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) != count:
        raise InvalidRenderedImageError("Rendered PNG is truncated")
    return bytes(data)


def validate_png_descriptor(
    descriptor: int,
    *,
    max_bytes: int,
    max_pixels: int,
) -> tuple[int, int]:
    """Validate PNG structure, CRC, dimensions and metadata-free chunk set."""

    size = os.fstat(descriptor).st_size
    if size < 33 or size > max_bytes:
        raise InvalidRenderedImageError("Rendered PNG size is outside limits")
    os.lseek(descriptor, 0, os.SEEK_SET)
    if _read_exact(descriptor, len(PNG_SIGNATURE)) != PNG_SIGNATURE:
        raise InvalidRenderedImageError("Rendered output is not PNG")

    width = height = 0
    saw_ihdr = False
    saw_idat = False
    saw_iend = False
    consumed = len(PNG_SIGNATURE)
    chunk_index = 0

    while consumed < size:
        length_raw = _read_exact(descriptor, 4)
        chunk_length = struct.unpack(">I", length_raw)[0]
        chunk_type = _read_exact(descriptor, 4)
        consumed += 8
        if chunk_length > max_bytes or consumed + chunk_length + 4 > size:
            raise InvalidRenderedImageError("Rendered PNG chunk is outside limits")
        if chunk_type not in _ALLOWED_PNG_CHUNKS:
            raise InvalidRenderedImageError("Rendered PNG contains disallowed metadata")
        if chunk_index == 0 and chunk_type != b"IHDR":
            raise InvalidRenderedImageError("Rendered PNG does not start with IHDR")

        crc_value = zlib.crc32(chunk_type)
        remaining = chunk_length
        ihdr_data = bytearray()
        while remaining:
            block = os.read(descriptor, min(64 * 1024, remaining))
            if not block:
                raise InvalidRenderedImageError("Rendered PNG chunk is truncated")
            remaining -= len(block)
            consumed += len(block)
            crc_value = zlib.crc32(block, crc_value)
            if chunk_type == b"IHDR":
                ihdr_data.extend(block)
        expected_crc = struct.unpack(">I", _read_exact(descriptor, 4))[0]
        consumed += 4
        if crc_value & 0xFFFFFFFF != expected_crc:
            raise InvalidRenderedImageError("Rendered PNG CRC is invalid")

        if chunk_type == b"IHDR":
            if saw_ihdr or chunk_length != 13:
                raise InvalidRenderedImageError("Rendered PNG IHDR is invalid")
            width, height = struct.unpack(">II", ihdr_data[:8])
            if width < 1 or height < 1 or width * height > max_pixels:
                raise InvalidRenderedImageError("Rendered PNG dimensions are outside limits")
            saw_ihdr = True
        elif chunk_type == b"IDAT":
            if not saw_ihdr or saw_iend:
                raise InvalidRenderedImageError("Rendered PNG IDAT order is invalid")
            saw_idat = True
        elif chunk_type == b"IEND":
            if chunk_length != 0 or not saw_idat:
                raise InvalidRenderedImageError("Rendered PNG IEND is invalid")
            saw_iend = True
            if consumed != size:
                raise InvalidRenderedImageError("Rendered PNG has trailing data")
            break
        chunk_index += 1

    if not saw_ihdr or not saw_idat or not saw_iend:
        raise InvalidRenderedImageError("Rendered PNG is incomplete")
    os.lseek(descriptor, 0, os.SEEK_SET)
    return width, height
