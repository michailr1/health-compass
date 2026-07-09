"""Add fail-closed account-linking intents and verified-email lookup helpers.

Revision ID: 0023
Revises: 0022
"""

from __future__ import annotations

from alembic import op

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None

S = "health_compass"
R = "health_compass_rls_definer"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        DO $$
        BEGIN
          IF NOT EXISTS (
            SELECT 1
            FROM pg_roles
            WHERE rolname = '{R}'
              AND rolbypassrls
              AND NOT rolcanlogin
          ) THEN
            RAISE EXCEPTION
              'Provision first: CREATE ROLE {R} NOLOGIN BYPASSRLS; '
              'GRANT {R} TO health_compass_migrator';
          END IF;
        END $$;
        """
    )

    op.execute(
        f"""
        CREATE TABLE {S}.account_link_intents (
          id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
          flow_type varchar(64) NOT NULL,
          status varchar(32) NOT NULL DEFAULT 'pending_confirmation',
          normalized_email varchar(320) NOT NULL,
          candidate_user_id uuid NOT NULL
            REFERENCES {S}.users(id) ON DELETE CASCADE,
          initiating_provider varchar(64) NOT NULL,
          initiating_subject varchar(255) NOT NULL,
          required_provider varchar(64) NOT NULL,
          required_subject varchar(255) NULL,
          initiating_claims jsonb NULL,
          browser_binding_hash varchar(128) NOT NULL,
          state_hash varchar(128) NULL,
          nonce_hash varchar(128) NULL,
          pkce_verifier_hash varchar(128) NULL,
          created_ip varchar(45) NULL,
          user_agent text NULL,
          failure_count integer NOT NULL DEFAULT 0,
          version integer NOT NULL DEFAULT 1,
          created_at timestamptz NOT NULL DEFAULT now(),
          expires_at timestamptz NOT NULL,
          completed_at timestamptz NULL,
          declined_at timestamptz NULL,
          CONSTRAINT ck_account_link_intents_flow_type CHECK (
            flow_type IN (
              'google_first_email_existing',
              'email_first_google_existing',
              'settings_add_google',
              'settings_add_email'
            )
          ),
          CONSTRAINT ck_account_link_intents_status CHECK (
            status IN (
              'pending_confirmation',
              'completed',
              'declined',
              'expired',
              'cancelled'
            )
          ),
          CONSTRAINT ck_account_link_intents_initiating_provider CHECK (
            initiating_provider IN ('google', 'email')
          ),
          CONSTRAINT ck_account_link_intents_required_provider CHECK (
            required_provider IN ('google', 'email')
          ),
          CONSTRAINT ck_account_link_intents_distinct_providers CHECK (
            initiating_provider <> required_provider
          ),
          CONSTRAINT ck_account_link_intents_expiry CHECK (
            expires_at > created_at
          ),
          CONSTRAINT ck_account_link_intents_completion CHECK (
            (status = 'completed' AND completed_at IS NOT NULL)
            OR (status <> 'completed' AND completed_at IS NULL)
          ),
          CONSTRAINT ck_account_link_intents_decline CHECK (
            (status = 'declined' AND declined_at IS NOT NULL)
            OR (status <> 'declined' AND declined_at IS NULL)
          ),
          CONSTRAINT ck_account_link_intents_failure_count CHECK (
            failure_count >= 0
          ),
          CONSTRAINT ck_account_link_intents_version CHECK (
            version > 0
          )
        )
        """
    )
    op.execute(
        f"CREATE INDEX ix_account_link_intents_expiry "
        f"ON {S}.account_link_intents (status, expires_at)"
    )
    op.execute(
        f"CREATE INDEX ix_account_link_intents_candidate "
        f"ON {S}.account_link_intents (candidate_user_id, created_at DESC)"
    )
    op.execute(
        f"CREATE INDEX ix_account_link_intents_email_created "
        f"ON {S}.account_link_intents (normalized_email, created_at DESC)"
    )

    op.execute(f"ALTER TABLE {S}.account_link_intents ENABLE ROW LEVEL SECURITY")
    op.execute(f"ALTER TABLE {S}.account_link_intents FORCE ROW LEVEL SECURITY")
    op.execute(
        f"CREATE POLICY account_link_intents_fail_closed "
        f"ON {S}.account_link_intents AS RESTRICTIVE FOR ALL "
        f"USING (false) WITH CHECK (false)"
    )
    op.execute(f"REVOKE ALL ON {S}.account_link_intents FROM PUBLIC")
    op.execute(f"REVOKE ALL ON {S}.account_link_intents FROM {APP}")
    op.execute(
        f"GRANT SELECT, INSERT, UPDATE, DELETE "
        f"ON {S}.account_link_intents TO {R}"
    )

    # The helpers deliberately expose only scalar candidate information.
    # A matching email never links accounts by itself.
    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_count_verified_email_users(
          lookup_email text
        ) RETURNS integer
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          SELECT count(DISTINCT ui.user_id)::integer
          FROM {S}.user_identities ui
          JOIN {S}.users u ON u.id = ui.user_id
          WHERE u.status = 'active'
            AND (
              (
                ui.provider = 'email'
                AND lower(btrim(ui.subject)) = lower(btrim(lookup_email))
                AND ui.claims ->> 'email_verified' = 'true'
              )
              OR
              (
                ui.provider = 'google'
                AND lower(btrim(ui.claims ->> 'email')) = lower(btrim(lookup_email))
                AND ui.claims ->> 'email_verified' = 'true'
              )
            )
        $$
        """
    )
    op.execute(
        f"ALTER FUNCTION {S}.app_count_verified_email_users(text) OWNER TO {R}"
    )
    op.execute(
        f"ALTER FUNCTION {S}.app_count_verified_email_users(text) "
        f"SET row_security = off"
    )

    op.execute(f"GRANT CREATE ON SCHEMA {S} TO {R}")
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {S}.app_lookup_single_verified_email_user(
          lookup_email text
        ) RETURNS uuid
        LANGUAGE sql
        STABLE
        SECURITY DEFINER
        SET search_path = ''
        AS $$
          WITH candidates AS (
            SELECT DISTINCT ui.user_id
            FROM {S}.user_identities ui
            JOIN {S}.users u ON u.id = ui.user_id
            WHERE u.status = 'active'
              AND (
                (
                  ui.provider = 'email'
                  AND lower(btrim(ui.subject)) = lower(btrim(lookup_email))
                  AND ui.claims ->> 'email_verified' = 'true'
                )
                OR
                (
                  ui.provider = 'google'
                  AND lower(btrim(ui.claims ->> 'email')) = lower(btrim(lookup_email))
                  AND ui.claims ->> 'email_verified' = 'true'
                )
              )
          )
          SELECT (array_agg(user_id))[1]
          FROM candidates
          HAVING count(*) = 1
        $$
        """
    )
    op.execute(
        f"ALTER FUNCTION {S}.app_lookup_single_verified_email_user(text) OWNER TO {R}"
    )
    op.execute(
        f"ALTER FUNCTION {S}.app_lookup_single_verified_email_user(text) "
        f"SET row_security = off"
    )
    op.execute(f"REVOKE CREATE ON SCHEMA {S} FROM {R}")

    for signature in (
        f"{S}.app_count_verified_email_users(text)",
        f"{S}.app_lookup_single_verified_email_user(text)",
    ):
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION "
        f"{S}.app_lookup_single_verified_email_user(text) FROM {APP}"
    )
    op.execute(
        f"REVOKE EXECUTE ON FUNCTION "
        f"{S}.app_count_verified_email_users(text) FROM {APP}"
    )
    op.execute(
        f"DROP FUNCTION IF EXISTS "
        f"{S}.app_lookup_single_verified_email_user(text)"
    )
    op.execute(
        f"DROP FUNCTION IF EXISTS {S}.app_count_verified_email_users(text)"
    )
    op.execute(f"REVOKE ALL ON {S}.account_link_intents FROM {R}")
    op.execute(f"DROP TABLE {S}.account_link_intents")
