"""Unit tests for Clinical Context dictionary helpers."""

from app.services.clinical_dictionary import normalize_search_text


def test_normalize_search_text_trims_casefolds_and_collapses_spaces() -> None:
    assert normalize_search_text("  ГОЛОВНАЯ   Боль  ") == "головная боль"


def test_normalize_search_text_normalizes_yo_and_punctuation() -> None:
    assert normalize_search_text("  Ёлка—пыльца / реакция  ") == "елка пыльца реакция"


def test_normalize_search_text_normalizes_unicode_compatibility_forms() -> None:
    assert normalize_search_text("Витамин Ｄ３") == "витамин d3"


def test_normalize_search_text_keeps_letters_and_numbers() -> None:
    assert normalize_search_text("Омега-3 EPA/DHA") == "омега 3 epa dha"
