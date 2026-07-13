"""Extend the audit action vocabulary for hardened E3 functions.

Revision ID: 0062
Revises: 0061

The original E3 migration used the historical underscore naming convention.
The hardened correction/erasure functions use explicit resource.action names.
Both remain allow-listed so migration history and the hardened runtime are
valid without weakening the closed audit vocabulary.
"""

from __future__ import annotations

from alembic import op

revision = "0062"
down_revision = "0061"
branch_labels = None
depends_on = None

S = "health_compass"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        DECLARE
          existing_expression text;
        BEGIN
          SELECT pg_catalog.pg_get_expr(c.conbin, c.conrelid)
          INTO existing_expression
          FROM pg_catalog.pg_constraint c
          JOIN pg_catalog.pg_class t ON t.oid = c.conrelid
          JOIN pg_catalog.pg_namespace n ON n.oid = t.relnamespace
          WHERE n.nspname = '{S}'
            AND t.relname = 'profile_audit_events'
            AND c.conname = 'ck_profile_audit_action'
            AND c.contype = 'c';

          IF existing_expression IS NULL THEN
            RAISE EXCEPTION 'Audit action constraint not found';
          END IF;

          EXECUTE 'ALTER TABLE {S}.profile_audit_events '
                  'DROP CONSTRAINT ck_profile_audit_action';
          EXECUTE pg_catalog.format(
            'ALTER TABLE {S}.profile_audit_events '
            'ADD CONSTRAINT ck_profile_audit_action CHECK ((%s) OR action IN ('
            '''lab.observation.corrected'','
            '''lab.observation.erased''))',
            existing_expression
          );
        END $$;
        """
    )


def downgrade() -> None:
    # Intentionally keep the additive closed vocabulary when stepping back to
    # 0061. The 0061 hardened functions still emit these values, so removing
    # them would make that revision internally invalid. A complete downgrade
    # through 0059 restores the pre-E3 constraint.
    pass
