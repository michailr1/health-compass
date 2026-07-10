"""Add observable condition timing fields.

Revision ID: 0044
Revises: 0043
"""

from __future__ import annotations

from alembic import op

revision = "0044"
down_revision = "0043"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "ADD COLUMN onset_timing varchar(32)"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "ADD COLUMN presence_pattern varchar(32)"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "ADD CONSTRAINT ck_profile_conditions_onset_timing "
        "CHECK (onset_timing IS NULL OR onset_timing IN ('recent','long_ago','unknown'))"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "ADD CONSTRAINT ck_profile_conditions_presence_pattern "
        "CHECK (presence_pattern IS NULL OR presence_pattern IN ('yes','resolved','recurring','unknown'))"
    )
    op.execute(
        f"GRANT UPDATE (onset_timing, presence_pattern) "
        f"ON {S}.profile_conditions TO {APP}"
    )


def downgrade() -> None:
    op.execute(
        f"REVOKE UPDATE (onset_timing, presence_pattern) "
        f"ON {S}.profile_conditions FROM {APP}"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "DROP CONSTRAINT ck_profile_conditions_presence_pattern"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions "
        "DROP CONSTRAINT ck_profile_conditions_onset_timing"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions DROP COLUMN presence_pattern"
    )
    op.execute(
        f"ALTER TABLE {S}.profile_conditions DROP COLUMN onset_timing"
    )
