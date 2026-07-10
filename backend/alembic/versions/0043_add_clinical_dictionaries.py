"""Add curated Clinical Context dictionaries.

Revision ID: 0043
Revises: 0042
"""

from __future__ import annotations

from alembic import op

revision = "0043"
down_revision = "0042"
branch_labels = None
depends_on = None

S = "health_compass"
APP = "health_compass_app"


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE {S}.clinical_dictionary_concepts (
          id uuid PRIMARY KEY,
          domain varchar(64) NOT NULL,
          display_name varchar(255) NOT NULL,
          normalized_text varchar(255) NOT NULL,
          qualifier varchar(255),
          source_system varchar(64) NOT NULL DEFAULT 'health_compass',
          source_code varchar(128),
          is_active boolean NOT NULL DEFAULT true,
          created_at timestamptz NOT NULL DEFAULT now(),
          updated_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT ck_clinical_dictionary_domain CHECK (
            domain IN ('condition_or_symptom','allergy_or_intolerance','medication','supplement')
          ),
          CONSTRAINT uq_clinical_dictionary_domain_name UNIQUE (domain, normalized_text)
        )
        """
    )
    op.execute(
        f"""
        CREATE TABLE {S}.clinical_dictionary_aliases (
          id uuid PRIMARY KEY,
          concept_id uuid NOT NULL REFERENCES {S}.clinical_dictionary_concepts(id) ON DELETE CASCADE,
          alias_text varchar(255) NOT NULL,
          normalized_text varchar(255) NOT NULL,
          created_at timestamptz NOT NULL DEFAULT now(),
          CONSTRAINT uq_clinical_dictionary_alias UNIQUE (concept_id, normalized_text)
        )
        """
    )
    op.execute(f"CREATE INDEX ix_clinical_dictionary_concepts_search ON {S}.clinical_dictionary_concepts(domain, normalized_text)")
    op.execute(f"CREATE INDEX ix_clinical_dictionary_aliases_search ON {S}.clinical_dictionary_aliases(normalized_text)")

    for table in (
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
    ):
        op.execute(
            f"ALTER TABLE {S}.{table} ADD COLUMN canonical_concept_id uuid "
            f"REFERENCES {S}.clinical_dictionary_concepts(id)"
        )
        op.execute(f"GRANT UPDATE (canonical_concept_id) ON {S}.{table} TO {APP}")

    op.execute(f"GRANT SELECT ON {S}.clinical_dictionary_concepts TO {APP}")
    op.execute(f"GRANT SELECT ON {S}.clinical_dictionary_aliases TO {APP}")
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {S}.clinical_dictionary_concepts FROM {APP}")
    op.execute(f"REVOKE INSERT, UPDATE, DELETE ON {S}.clinical_dictionary_aliases FROM {APP}")

    seed = [
        ('11111111-1111-4111-8111-111111111101','condition_or_symptom','Головная боль','головная боль',None),
        ('11111111-1111-4111-8111-111111111102','condition_or_symptom','Повышенное артериальное давление','повышенное артериальное давление','гипертония'),
        ('11111111-1111-4111-8111-111111111103','condition_or_symptom','Бронхиальная астма','бронхиальная астма',None),
        ('11111111-1111-4111-8111-111111111201','allergy_or_intolerance','Пенициллин','пенициллин',None),
        ('11111111-1111-4111-8111-111111111202','allergy_or_intolerance','Арахис','арахис',None),
        ('11111111-1111-4111-8111-111111111301','medication','Метформин','метформин',None),
        ('11111111-1111-4111-8111-111111111302','medication','Амлодипин','амлодипин',None),
        ('11111111-1111-4111-8111-111111111401','supplement','Магний','магний',None),
        ('11111111-1111-4111-8111-111111111402','supplement','Витамин D','витамин d',None)
    ]
    for concept_id, domain, display_name, normalized_text, qualifier in seed:
        q = "NULL" if qualifier is None else "'" + qualifier.replace("'", "''") + "'"
        op.execute(
            f"INSERT INTO {S}.clinical_dictionary_concepts "
            f"(id, domain, display_name, normalized_text, qualifier) VALUES "
            f"('{concept_id}','{domain}','{display_name}','{normalized_text}',{q}) "
            "ON CONFLICT DO NOTHING"
        )


def downgrade() -> None:
    for table in (
        "profile_conditions",
        "profile_allergies",
        "profile_medications",
        "profile_supplements",
    ):
        op.execute(f"REVOKE UPDATE (canonical_concept_id) ON {S}.{table} FROM {APP}")
        op.execute(f"ALTER TABLE {S}.{table} DROP COLUMN canonical_concept_id")
    op.execute(f"DROP TABLE {S}.clinical_dictionary_aliases")
    op.execute(f"DROP TABLE {S}.clinical_dictionary_concepts")
