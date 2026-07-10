"""Harden Clinical Context write invariants.

Revision ID: 0040
Revises: 0039
"""

from __future__ import annotations

from alembic import op

revision = "0040"
down_revision = "0039"
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
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.enforce_manual_clinical_write()
        RETURNS trigger
        LANGUAGE plpgsql
        SET search_path = ''
        AS $$
        BEGIN
          IF current_user = '{APP}' AND (
            NEW.source_type <> 'manual'
            OR NEW.confirmation_status <> 'confirmed'
          ) THEN
            RAISE EXCEPTION 'App writes must be manual and confirmed'
              USING ERRCODE = '42501';
          END IF;
          RETURN NEW;
        END
        $$
        """
    )
    op.execute(
        f"REVOKE ALL ON FUNCTION {S}.enforce_manual_clinical_write() FROM PUBLIC"
    )

    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER {table}_manual_write_guard "
            f"BEFORE INSERT OR UPDATE ON {S}.{table} "
            f"FOR EACH ROW EXECUTE FUNCTION {S}.enforce_manual_clinical_write()"
        )
        op.execute(f"DROP POLICY {table}_update ON {S}.{table}")
        op.execute(
            f"""
            CREATE POLICY {table}_update ON {S}.{table}
            FOR UPDATE
            USING (
              {S}.app_can_edit_profile(profile_id)
              AND voided_at IS NULL
            )
            WITH CHECK (
              {S}.app_can_edit_profile(profile_id)
              AND (
                voided_at IS NULL
                OR voided_by_user_id = {S}.app_current_user_id()
              )
            )
            """
        )


def downgrade() -> None:
    for table in TABLES:
        op.execute(f"DROP POLICY {table}_update ON {S}.{table}")
        op.execute(
            f"""
            CREATE POLICY {table}_update ON {S}.{table}
            FOR UPDATE
            USING ({S}.app_can_edit_profile(profile_id))
            WITH CHECK ({S}.app_can_edit_profile(profile_id))
            """
        )
        op.execute(
            f"DROP TRIGGER IF EXISTS {table}_manual_write_guard ON {S}.{table}"
        )

    op.execute(f"DROP FUNCTION {S}.enforce_manual_clinical_write()")
