"""Bounded local Tesseract execution and strict TSV parsing."""

from __future__ import annotations

import fcntl
import hashlib
import os
import re
import resource
import signal
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

_TSV_HEADER = (
    "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
    "left\ttop\twidth\theight\tconf\ttext"
)
_LANGUAGE_RE = re.compile(r"^[a-z]{3}(\+[a-z]{3}){0,4}$")
_VERSION_RE = re.compile(r"^tesseract\s+(?P<version>[0-9][A-Za-z0-9._+-]{0,63})$")


class OCRError(Exception):
    """Base class for content-free OCR failures."""


class OCRTimeoutError(OCRError):
    pass


class OCRProcessError(OCRError):
    pass


class OCROutputError(OCRError):
    pass


class OCRLanguageDataError(OCRError):
    pass


@dataclass(frozen=True)
class OCRLimits:
    timeout_seconds: int
    cpu_seconds: int
    memory_bytes: int
    max_output_bytes: int
    max_rows: int
    max_candidates: int
    max_candidate_chars: int
    max_candidate_words: int


@dataclass(frozen=True)
class OCRCandidateData:
    candidate_index: int
    original_text: str
    confidence_min: float
    confidence_mean: float
    left_px: int
    top_px: int
    width_px: int
    height_px: int
    word_count: int


@dataclass(frozen=True)
class OCRPageResult:
    descriptor: int
    engine_version: str
    traineddata_manifest_sha256: str


@dataclass(frozen=True)
class _Word:
    block: int
    paragraph: int
    line: int
    word: int
    left: int
    top: int
    width: int
    height: int
    confidence: float
    text: str


def _safe_traineddata_file(directory: Path, language: str) -> tuple[int, os.stat_result]:
    path = directory / f"{language}.traineddata"
    flags = os.O_RDONLY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise OCRLanguageDataError("Required OCR language data is unavailable") from exc
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(descriptor)
        raise OCRLanguageDataError("OCR language data must be a regular private file")
    if info.st_mode & (stat.S_IWGRP | stat.S_IWOTH):
        os.close(descriptor)
        raise OCRLanguageDataError("OCR language data permissions are unsafe")
    if info.st_size < 1 or info.st_size > 256 * 1024 * 1024:
        os.close(descriptor)
        raise OCRLanguageDataError("OCR language data size is outside limits")
    return descriptor, info


def traineddata_manifest_sha256(tessdata_directory: str, language_spec: str) -> str:
    """Hash exact language files without following symlinks."""

    if not _LANGUAGE_RE.fullmatch(language_spec):
        raise OCRLanguageDataError("Invalid OCR language specification")
    directory = Path(tessdata_directory).expanduser().resolve()
    digest = hashlib.sha256()
    for language in language_spec.split("+"):
        descriptor, info = _safe_traineddata_file(directory, language)
        try:
            digest.update(language.encode("ascii"))
            digest.update(b"\x00")
            digest.update(str(info.st_size).encode("ascii"))
            digest.update(b"\x00")
            while True:
                chunk = os.read(descriptor, 1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        finally:
            os.close(descriptor)
    return digest.hexdigest()


class TesseractOCR:
    """Run one safe page through a fixed local Tesseract command."""

    def __init__(
        self,
        *,
        executable_path: str,
        tessdata_directory: str,
        language_spec: str,
        psm: int,
        limits: OCRLimits,
    ) -> None:
        if not executable_path.startswith("/"):
            raise ValueError("Tesseract executable path must be absolute")
        if not Path(tessdata_directory).is_absolute():
            raise ValueError("Tesseract data directory must be absolute")
        if not _LANGUAGE_RE.fullmatch(language_spec):
            raise ValueError("Invalid OCR language specification")
        if psm not in {3, 4, 6, 11, 12}:
            raise ValueError("Unsupported OCR page segmentation mode")
        self.executable_path = executable_path
        self.tessdata_directory = tessdata_directory
        self.language_spec = language_spec
        self.psm = psm
        self.limits = limits

    @staticmethod
    def _new_memfd(name: str) -> int:
        if not hasattr(os, "memfd_create"):
            raise OCRProcessError("Anonymous memory files are unavailable")
        flags = getattr(os, "MFD_CLOEXEC", 0) | getattr(os, "MFD_ALLOW_SEALING", 0)
        return os.memfd_create(name, flags)

    @staticmethod
    def _seal_readonly(descriptor: int) -> None:
        if not hasattr(fcntl, "F_ADD_SEALS"):
            raise OCRProcessError("Memory-file sealing is unavailable")
        seals = (
            fcntl.F_SEAL_WRITE
            | fcntl.F_SEAL_GROW
            | fcntl.F_SEAL_SHRINK
            | fcntl.F_SEAL_SEAL
        )
        fcntl.fcntl(descriptor, fcntl.F_ADD_SEALS, seals)

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

    def _run(
        self,
        arguments: list[str],
        *,
        input_descriptor: int | None,
        output_limit: int,
    ) -> int:
        output_descriptor = self._new_memfd("hc-ocr-output")
        error_descriptor = self._new_memfd("hc-ocr-error")
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
                pass_fds=() if input_descriptor is None else (input_descriptor,),
                start_new_session=True,
                env={"PATH": "/usr/bin:/bin", "LANG": "C", "LC_ALL": "C"},
                preexec_fn=self._resource_limiter(output_limit),
            )
            try:
                return_code = process.wait(timeout=self.limits.timeout_seconds)
            except subprocess.TimeoutExpired as exc:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise OCRTimeoutError("OCR process exceeded its timeout") from exc
            finally:
                output_handle.close()
                error_handle.close()

            if return_code != 0:
                raise OCRProcessError("OCR process rejected the page")
            size = os.fstat(output_descriptor).st_size
            if size < 1 or size > output_limit:
                raise OCROutputError("OCR output size is outside limits")
            self._seal_readonly(output_descriptor)
            os.lseek(output_descriptor, 0, os.SEEK_SET)
            return output_descriptor
        except Exception:
            os.close(output_descriptor)
            raise
        finally:
            for handle in (output_handle, error_handle):
                try:
                    handle.close()
                except Exception:
                    pass
            os.close(error_descriptor)

    @staticmethod
    def _read_bounded_text(descriptor: int, max_bytes: int) -> str:
        size = os.fstat(descriptor).st_size
        if size < 1 or size > max_bytes:
            raise OCROutputError("OCR metadata output is outside limits")
        os.lseek(descriptor, 0, os.SEEK_SET)
        payload = bytearray()
        while len(payload) < size:
            chunk = os.read(descriptor, size - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
        if len(payload) != size:
            raise OCROutputError("OCR metadata output is truncated")
        try:
            return bytes(payload).decode("utf-8", errors="strict")
        except UnicodeDecodeError as exc:
            raise OCROutputError("OCR output is not valid UTF-8") from exc

    def version(self) -> str:
        descriptor = self._run(
            [self.executable_path, "--version"],
            input_descriptor=None,
            output_limit=64 * 1024,
        )
        try:
            first_line = self._read_bounded_text(descriptor, 64 * 1024).splitlines()[0]
        finally:
            os.close(descriptor)
        match = _VERSION_RE.fullmatch(first_line.strip())
        if match is None:
            raise OCRProcessError("Unexpected Tesseract version output")
        return match.group("version")

    def run_tsv(self, input_descriptor: int) -> OCRPageResult:
        manifest = traineddata_manifest_sha256(
            self.tessdata_directory,
            self.language_spec,
        )
        version = self.version()
        input_path = f"/proc/self/fd/{input_descriptor}"
        descriptor = self._run(
            [
                self.executable_path,
                input_path,
                "stdout",
                "--tessdata-dir",
                self.tessdata_directory,
                "--oem",
                "1",
                "--psm",
                str(self.psm),
                "-l",
                self.language_spec,
                "tsv",
            ],
            input_descriptor=input_descriptor,
            output_limit=self.limits.max_output_bytes,
        )
        return OCRPageResult(
            descriptor=descriptor,
            engine_version=version,
            traineddata_manifest_sha256=manifest,
        )

    def parse_tsv(
        self,
        descriptor: int,
        *,
        page_width: int,
        page_height: int,
    ) -> list[OCRCandidateData]:
        payload = self._read_bounded_text(descriptor, self.limits.max_output_bytes)
        lines = payload.splitlines()
        if not lines or lines[0] != _TSV_HEADER:
            raise OCROutputError("Unexpected OCR TSV header")
        if len(lines) - 1 > self.limits.max_rows:
            raise OCROutputError("OCR TSV row count exceeds limits")

        groups: dict[tuple[int, int, int], list[_Word]] = {}
        for row_number, line in enumerate(lines[1:], start=2):
            columns = line.split("\t", 11)
            if len(columns) != 12:
                raise OCROutputError("Malformed OCR TSV row")
            try:
                level = int(columns[0])
                page_num = int(columns[1])
                block = int(columns[2])
                paragraph = int(columns[3])
                line_num = int(columns[4])
                word_num = int(columns[5])
                left = int(columns[6])
                top = int(columns[7])
                width = int(columns[8])
                height = int(columns[9])
                confidence = float(columns[10])
            except ValueError as exc:
                raise OCROutputError("Invalid numeric OCR TSV field") from exc
            text = columns[11].strip()
            if level != 5:
                continue
            if page_num != 1 or block < 0 or paragraph < 0 or line_num < 0 or word_num < 0:
                raise OCROutputError("Invalid OCR TSV hierarchy")
            if confidence < 0 or not text:
                continue
            if confidence > 100:
                raise OCROutputError("Invalid OCR confidence")
            if left < 0 or top < 0 or width < 1 or height < 1:
                raise OCROutputError("Invalid OCR bounding box")
            if left + width > page_width or top + height > page_height:
                raise OCROutputError("OCR bounding box exceeds page dimensions")
            if len(text) > 512 or any(ord(char) < 32 or ord(char) == 127 for char in text):
                raise OCROutputError("Invalid OCR word text")
            key = (block, paragraph, line_num)
            groups.setdefault(key, []).append(
                _Word(
                    block=block,
                    paragraph=paragraph,
                    line=line_num,
                    word=word_num,
                    left=left,
                    top=top,
                    width=width,
                    height=height,
                    confidence=confidence,
                    text=text,
                )
            )

        candidates: list[OCRCandidateData] = []
        for key in sorted(groups):
            words = sorted(groups[key], key=lambda item: item.word)
            if not words:
                continue
            if len(words) > self.limits.max_candidate_words:
                raise OCROutputError("OCR candidate word count exceeds limits")
            text = " ".join(item.text for item in words)
            if not text or len(text) > self.limits.max_candidate_chars:
                raise OCROutputError("OCR candidate text exceeds limits")
            left = min(item.left for item in words)
            top = min(item.top for item in words)
            right = max(item.left + item.width for item in words)
            bottom = max(item.top + item.height for item in words)
            confidences = [item.confidence for item in words]
            candidates.append(
                OCRCandidateData(
                    candidate_index=len(candidates),
                    original_text=text,
                    confidence_min=min(confidences),
                    confidence_mean=sum(confidences) / len(confidences),
                    left_px=left,
                    top_px=top,
                    width_px=right - left,
                    height_px=bottom - top,
                    word_count=len(words),
                )
            )
            if len(candidates) > self.limits.max_candidates:
                raise OCROutputError("OCR candidate count exceeds limits")

        os.lseek(descriptor, 0, os.SEEK_SET)
        return candidates
