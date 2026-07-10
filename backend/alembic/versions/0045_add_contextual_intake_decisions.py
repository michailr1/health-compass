"""Add contextual intake decision audit.

Revision ID: 0045
Revises: 0044
"""

from __future__ import annotations

from alembic import op

revision = "0045"
down_revision = "0044"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.profile_intake_decisions (
          id uuid PRIMARY KEY,
          profile_id uuid NOT NULL REFERENCES {S}.health_profiles(id),
          prompt_key varchar(128) NOT NULL,
          context_type varchar(64) NOT NULL,
          decision varchar(32) NOT NULL,
          proposed_section varchar(32),
          analysis_scope_id uuid,
          decided_by_user_id uuid NOT NULL REFERENCES {S}.users(id),
          decided_at timestamptz NOT NULL DEFAULT now(),
          request_id varchar(128),
          CONSTRAINT ck_profile_intake_decision CHECK (
            decision IN ('save_to_profile','analysis_only','defer')
          ),
          CONSTRAINT ck_profile_intake_section CHECK (
            proposed_section IS NULL OR proposed_section IN (
              'conditions','allergies','medications','supplements'
            )
          ),
          CONSTRAINT ck_profile_intake_analysis_scope CHECK (
            (decision = 'analysis_only' AND analysis_scope_id IS NOT NULL)
            OR (decision <> 'analysis_only' AND analysis_scope_id IS NULL)
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_profile_intake_decisions_profile_time "
        f"ON {S}.profile_intake_decisions(profile_id, decided_at DESC)"
    )
    op.execute(f"ALTER TABLE {S}.profile_intake_decisions ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.profile_intake_decisions FORCE ROW LEVEL SECURITY")
    op.execute(f"GRANT SELECT, INSERT ON {S}.profile_intake_decisions TO {APP}")
    op.execute(f"REVOKE UPDATE, DELETE ON {S}.profile_intake_decisions FROM {APP}")
    op.execute(
        f"""
        CREATE POLICY intake_decisions_select_visible
        ON {S}.profile_intake_decisions
        FOR SELECT TO {APP}
        USING ({S}.app_can_view_profile(profile_id))
        """
    )
    op.execute(
        f"""
        CREATE POLICY intake_decisions_insert_editable
        ON {S}.profile_intake_decisions
        FOR INSERT TO {APP}
        WITH CHECK (
          {S}.app_can_edit_profile(profile_id)
          AND decided_by_user_id = {S}.app_current_user_id()
        )
        """
    )


def downgrade() -> None:
    op.execute(f"DROP TABLE {S}.profile_intake_decisions")
