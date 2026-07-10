"""Revoke application DELETE privileges from Clinical Context tables.

Revision ID: 0041
Revises: 0040
"""

from __future__ import annotations

from alembic import op

revision = "0041"
down_revision = "0040"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"
TABLES = (
    "profile_conditions",
    "profile_allergies",
    "profile_medications",
    "profile_supplements",
    "profile_clinical_safety_flags",
    "profile_clinical_reviews",
)


def upgrade() -> None:
    tables = ", ".join(f"{S}.{table}" for table in TABLES)
    op.execute(f"REVOKE DELETE ON TABLE {tables} FROM {APP}")


def downgrade() -> None:
    # Security hardening is intentionally not reversed. Restoring DELETE would
    # violate the Clinical Context invariant that records are voided, never
    # physically removed by the application role.
    pass
