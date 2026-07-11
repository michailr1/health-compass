"""HC-015 Slice D: seed import is idempotent on real database business keys.

CR-07: alias upsert must merge on (concept_id, normalized_text) — the actual
unique constraint — so a pre-existing alias row with a different UUID is
updated in place instead of crashing or duplicating.
"""

from __future__ import annotations

import os
import uuid

import psycopg
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.services.clinical_dictionary_seed import (
    SeedAlias,
    SeedConcept,
    SeedManifest,
    concept_uuid,
    upsert_seed_manifest,
)

pytestmark = pytest.mark.integration

ADMIN_DSN = os.getenv("HC_TEST_DATABASE_ADMIN_DSN")


def _admin_dsn() -> str:
    if not ADMIN_DSN:
        pytest.skip("HC_TEST_DATABASE_ADMIN_DSN is not configured")
    return ADMIN_DSN


def _migrator_async_url() -> str:
    url = os.environ.get("TEST_DATABASE_MIGRATOR_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_MIGRATOR_URL is not configured")
    return url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)


def _manifest() -> SeedManifest:
    concept = SeedConcept(
        domain="condition_or_symptom",
        display_name="Тестовая мигрень HC-015",
        source_system="health_compass_ru_curated",
        source_code="condition-test-migraine-hc015",
        qualifier=None,
        locale="ru-RU",
        country="RU",
        aliases=(
            SeedAlias(text="Migraine HC015", language="en", kind="international"),
            SeedAlias(text="Тестовая гемикрания", language="ru", kind="synonym"),
        ),
    )
    return SeedManifest(version="hc015-test", source_label="hc015-test", concepts=(concept,))


def _dictionary_state(concept_id: uuid.UUID) -> tuple[int, list[tuple[str, str]]]:
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        concepts = conn.execute(
            "SELECT count(*) FROM health_compass.clinical_dictionary_concepts WHERE id = %s",
            (concept_id,),
        ).fetchone()[0]
        aliases = conn.execute(
            """
            SELECT id::text, alias_text
            FROM health_compass.clinical_dictionary_aliases
            WHERE concept_id = %s
            ORDER BY normalized_text
            """,
            (concept_id,),
        ).fetchall()
    return concepts, aliases


def _cleanup(concept_id: uuid.UUID) -> None:
    with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
        conn.execute(
            "DELETE FROM health_compass.clinical_dictionary_aliases WHERE concept_id = %s",
            (concept_id,),
        )
        conn.execute(
            "DELETE FROM health_compass.clinical_dictionary_concepts WHERE id = %s",
            (concept_id,),
        )


async def _run_import(manifest: SeedManifest) -> dict[str, int]:
    engine = create_async_engine(_migrator_async_url())
    try:
        factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with factory() as session:
            async with session.begin():
                return await upsert_seed_manifest(session, manifest)
    finally:
        await engine.dispose()


async def test_repeated_import_is_idempotent_and_preserves_ids() -> None:
    manifest = _manifest()
    concept_id = concept_uuid(manifest.concepts[0])
    try:
        first = await _run_import(manifest)
        assert first == {"concepts": 1, "aliases": 2}
        concepts, aliases_before = _dictionary_state(concept_id)
        assert concepts == 1
        assert len(aliases_before) == 2

        second = await _run_import(manifest)
        assert second == {"concepts": 1, "aliases": 2}
        concepts, aliases_after = _dictionary_state(concept_id)
        assert concepts == 1
        assert aliases_after == aliases_before
    finally:
        _cleanup(concept_id)


async def test_pre_existing_alias_with_different_uuid_is_merged_in_place() -> None:
    manifest = _manifest()
    concept_id = concept_uuid(manifest.concepts[0])
    foreign_alias_id = uuid.uuid4()
    try:
        await _run_import(manifest)

        # Simulate an alias row created outside the importer: same business
        # key (concept_id, normalized_text), different UUID and casing.
        with psycopg.connect(_admin_dsn(), autocommit=True) as conn:
            conn.execute(
                "DELETE FROM health_compass.clinical_dictionary_aliases "
                "WHERE concept_id = %s AND normalized_text = %s",
                (concept_id, "migraine hc015"),
            )
            conn.execute(
                """
                INSERT INTO health_compass.clinical_dictionary_aliases
                  (id, concept_id, alias_text, normalized_text)
                VALUES (%s, %s, 'MIGRAINE HC015 LEGACY', 'migraine hc015')
                """,
                (foreign_alias_id, concept_id),
            )

        result = await _run_import(manifest)
        assert result == {"concepts": 1, "aliases": 2}

        _, aliases = _dictionary_state(concept_id)
        by_id = {alias_id: text for alias_id, text in aliases}
        # The foreign row keeps its UUID but is refreshed to the seed text,
        # and no duplicate business key appears.
        assert by_id[str(foreign_alias_id)] == "Migraine HC015"
        assert len(aliases) == 2
    finally:
        _cleanup(concept_id)
