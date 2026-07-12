"""Unit tests for bounded Tesseract TSV parsing and language provenance."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from app.ocr.tesseract import (
    OCRLanguageDataError,
    OCRLimits,
    OCROutputError,
    TesseractOCR,
    traineddata_manifest_sha256,
)


def _ocr() -> TesseractOCR:
    return TesseractOCR(
        executable_path="/usr/bin/tesseract",
        tessdata_directory="/usr/share/tesseract-ocr/5/tessdata",
        language_spec="rus+eng",
        psm=6,
        limits=OCRLimits(
            timeout_seconds=10,
            cpu_seconds=5,
            memory_bytes=128 * 1024 * 1024,
            max_output_bytes=1024 * 1024,
            max_rows=100,
            max_candidates=20,
            max_candidate_chars=200,
            max_candidate_words=20,
        ),
    )


def _descriptor(payload: str) -> int:
    flags = getattr(os, "MFD_CLOEXEC", 0) | getattr(os, "MFD_ALLOW_SEALING", 0)
    descriptor = os.memfd_create("hc-ocr-test", flags)
    os.write(descriptor, payload.encode("utf-8"))
    os.lseek(descriptor, 0, os.SEEK_SET)
    return descriptor


def _header() -> str:
    return (
        "level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\t"
        "left\ttop\twidth\theight\tconf\ttext"
    )


def test_tsv_words_are_aggregated_without_rewriting() -> None:
    payload = "\n".join(
        [
            _header(),
            "5\t1\t1\t1\t1\t1\t10\t20\t30\t12\t91.5\tГлюкоза",
            "5\t1\t1\t1\t1\t2\t45\t20\t20\t12\t88.0\t5.4",
            "5\t1\t1\t1\t2\t1\t10\t45\t40\t12\t75.0\tммоль/л",
        ]
    )
    descriptor = _descriptor(payload)
    try:
        candidates = _ocr().parse_tsv(
            descriptor,
            page_width=200,
            page_height=100,
        )
    finally:
        os.close(descriptor)

    assert [item.original_text for item in candidates] == [
        "Глюкоза 5.4",
        "ммоль/л",
    ]
    assert candidates[0].left_px == 10
    assert candidates[0].width_px == 55
    assert candidates[0].confidence_min == 88.0
    assert candidates[0].word_count == 2


def test_malformed_header_and_out_of_page_box_fail_closed() -> None:
    descriptor = _descriptor("bad\theader\n")
    try:
        with pytest.raises(OCROutputError, match="header"):
            _ocr().parse_tsv(descriptor, page_width=100, page_height=100)
    finally:
        os.close(descriptor)

    payload = "\n".join(
        [
            _header(),
            "5\t1\t1\t1\t1\t1\t90\t10\t20\t10\t90\tvalue",
        ]
    )
    descriptor = _descriptor(payload)
    try:
        with pytest.raises(OCROutputError, match="dimensions"):
            _ocr().parse_tsv(descriptor, page_width=100, page_height=100)
    finally:
        os.close(descriptor)


def test_control_characters_and_excessive_rows_are_rejected() -> None:
    payload = "\n".join(
        [
            _header(),
            "5\t1\t1\t1\t1\t1\t1\t1\t10\t10\t90\tbad\x01text",
        ]
    )
    descriptor = _descriptor(payload)
    try:
        with pytest.raises(OCROutputError, match="word text"):
            _ocr().parse_tsv(descriptor, page_width=100, page_height=100)
    finally:
        os.close(descriptor)

    rows = [
        f"5\t1\t1\t1\t{index}\t1\t1\t1\t1\t1\t90\tx"
        for index in range(101)
    ]
    descriptor = _descriptor("\n".join([_header(), *rows]))
    try:
        with pytest.raises(OCROutputError, match="row count"):
            _ocr().parse_tsv(descriptor, page_width=100, page_height=100)
    finally:
        os.close(descriptor)


def test_traineddata_manifest_is_stable_and_rejects_symlinks(tmp_path: Path) -> None:
    (tmp_path / "rus.traineddata").write_bytes(b"rus-model")
    (tmp_path / "eng.traineddata").write_bytes(b"eng-model")
    first = traineddata_manifest_sha256(str(tmp_path), "rus+eng")
    second = traineddata_manifest_sha256(str(tmp_path), "rus+eng")
    assert first == second
    assert len(first) == 64

    (tmp_path / "eng.traineddata").unlink()
    (tmp_path / "real.traineddata").write_bytes(b"eng-model")
    (tmp_path / "eng.traineddata").symlink_to(tmp_path / "real.traineddata")
    with pytest.raises(OCRLanguageDataError):
        traineddata_manifest_sha256(str(tmp_path), "rus+eng")
