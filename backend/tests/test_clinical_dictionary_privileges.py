"""Integration tests for global Clinical Context dictionary privileges."""

from __future__ import annotations

import os
from urllib.parse import urlsplit

import pytest
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.integration


def _migrator_url() -> str:
    url = os.environ.get("TEST_DATABASE_MIGRATOR_URL", "").strip()
    if not url:
        pytest.skip("TEST_DATABASE_MIGRATOR_URL is not configured")
    database_name = urlsplit(
        url.replace("postgresql+psycopg://", "postgresql://", 1)
    ).path.lstrip("/")
    if not database_name.endswith("_test"):
        pytest.fail("dictionary privilege tests require a *_test database")
    return url


def test_app_role_can_only_read_global_dictionary() -> None:
    engine = create_engine(_migrator_url())
    try:
        with engine.connect() as connection:
            privileges = {
                privilege: connection.execute(
                    text(
                        "SELECT has_table_privilege("
                        "'health_compass_app', "
                        "'health_compass.clinical_dictionary_concepts', "
                        ":privilege)"
                    ),
                    {"privilege": privilege},
                ).scalar_one()
                for privilege in ("SELECT", "INSERT", "UPDATE", "DELETE")
            }
            assert privileges == {
                "SELECT": True,
                "INSERT": False,
                "UPDATE": False,
                "DELETE": False,
            }

            aliases_select = connection.execute(
                text(
                    "SELECT has_table_privilege("
                    "'health_compass_app', "
                    "'health_compass.clinical_dictionary_aliases', "
                    "'SELECT')"
                )
            ).scalar_one()
            assert aliases_select is True
    finally:
        engine.dispose()


def test_dictionary_seed_is_deterministic() -> None:
    engine = create_engine(_migrator_url())
    try:
        with engine.connect() as connection:
            names = connection.execute(
                text(
                    "SELECT display_name "
                    "FROM health_compass.clinical_dictionary_concepts "
                    "ORDER BY display_name"
                )
            ).scalars().all()
            assert "Головная боль" in names
            assert "Метформин" in names
            assert "Магний" in names
    finally:
        engine.dispose()
