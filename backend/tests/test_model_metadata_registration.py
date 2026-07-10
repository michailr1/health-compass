"""Regression coverage for model registration required by Clinical Context FKs."""

import app.models  # noqa: F401
import app.models.clinical_context  # noqa: F401
from app.db.base import Base


def test_clinical_dictionary_foreign_keys_resolve_in_shared_metadata() -> None:
    table_names = {table.fullname for table in Base.metadata.sorted_tables}

    assert "health_compass.clinical_dictionary_concepts" in table_names
    assert "health_compass.clinical_dictionary_aliases" in table_names

    for table_name in (
        "health_compass.profile_conditions",
        "health_compass.profile_allergies",
        "health_compass.profile_medications",
        "health_compass.profile_supplements",
    ):
        assert table_name in table_names

    for table_name in (
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
    ):
        table = Base.metadata.tables[f"health_compass.{table_name}"]
        foreign_keys = {fk.target_fullname for fk in table.c.canonical_concept_id.foreign_keys}
        assert foreign_keys == {"health_compass.clinical_dictionary_concepts.id"}
