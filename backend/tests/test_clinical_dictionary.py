"""Unit tests for Clinical Context dictionary helpers."""

from app.services.clinical_dictionary import normalize_search_text


def test_normalize_search_text_trims_casefolds_and_collapses_spaces() -> None:
    assert normalize_search_text("  ГОЛОВНАЯ   Боль  ") == "головная боль"


def test_normalize_search_text_preserves_meaningful_characters() -> None:
    assert normalize_search_text("Витамин D3") == "витамин d3"
