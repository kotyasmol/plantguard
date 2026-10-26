"""Create the initial PlantGuard domain schema.

Revision ID: 0001_initial_domain
Revises:
Create Date: 2026-10-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_initial_domain"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "plants",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("nickname", sa.String(length=100), nullable=False),
        sa.Column("species_scientific_name", sa.String(length=160), nullable=True),
        sa.Column("species_common_name", sa.String(length=160), nullable=True),
        sa.Column(
            "species_status",
            sa.String(length=20),
            server_default=sa.text("'unconfirmed'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "species_status IN ('unconfirmed', 'suggested', 'confirmed')",
            name="ck_plants_species_status",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plants"),
    )

    op.create_table(
        "observations",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("humidity_pct", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column("temperature_c", sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "humidity_pct IS NULL OR humidity_pct BETWEEN 0 AND 100",
            name="ck_observations_humidity_range",
        ),
        sa.CheckConstraint(
            "temperature_c IS NULL OR temperature_c BETWEEN -50 AND 70",
            name="ck_observations_temperature_range",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name="fk_observations_plant_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_observations"),
    )
    op.create_index(
        "ix_observations_plant_observed_at",
        "observations",
        ["plant_id", "observed_at"],
    )

    op.create_table(
        "photos",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=64), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("length(checksum_sha256) = 64", name="ck_photos_checksum_length"),
        sa.CheckConstraint("size_bytes > 0", name="ck_photos_size_positive"),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.id"],
            name="fk_photos_observation_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_photos"),
        sa.UniqueConstraint("storage_key", name="uq_photos_storage_key"),
    )
    op.create_index("ix_photos_observation_id", "photos", ["observation_id"])

    op.create_table(
        "care_events",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("action_type", sa.String(length=24), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action_type IN ('watered', 'fertilized', 'repotted', 'moved', 'pruned', "
            "'treated', 'other')",
            name="ck_care_events_action_type",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name="fk_care_events_plant_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_care_events"),
    )
    op.create_index(
        "ix_care_events_plant_performed_at", "care_events", ["plant_id", "performed_at"]
    )

    op.create_table(
        "assessments",
        sa.Column(
            "id",
            sa.Uuid(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("observation_id", sa.Uuid(), nullable=False),
        sa.Column("previous_assessment_id", sa.Uuid(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("identified_scientific_name", sa.String(length=160), nullable=True),
        sa.Column("identification_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("finding_code", sa.String(length=80), nullable=True),
        sa.Column("finding_confidence", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "risk_level",
            sa.String(length=16),
            server_default=sa.text("'unknown'"),
            nullable=False,
        ),
        sa.Column("explanation", sa.Text(), nullable=True),
        sa.Column("model_version", sa.String(length=120), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "identification_confidence IS NULL OR identification_confidence BETWEEN 0 AND 1",
            name="ck_assessments_identification_confidence",
        ),
        sa.CheckConstraint(
            "finding_confidence IS NULL OR finding_confidence BETWEEN 0 AND 1",
            name="ck_assessments_finding_confidence",
        ),
        sa.CheckConstraint(
            "risk_level IN ('unknown', 'low', 'medium', 'high')",
            name="ck_assessments_risk_level",
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'succeeded', 'needs_review', 'failed')",
            name="ck_assessments_status",
        ),
        sa.ForeignKeyConstraint(
            ["observation_id"],
            ["observations.id"],
            name="fk_assessments_observation_id",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["previous_assessment_id"],
            ["assessments.id"],
            name="fk_assessments_previous_assessment_id",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_assessments"),
    )
    op.create_index(
        "ix_assessments_observation_created_at",
        "assessments",
        ["observation_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_assessments_observation_created_at", table_name="assessments")
    op.drop_table("assessments")
    op.drop_index("ix_care_events_plant_performed_at", table_name="care_events")
    op.drop_table("care_events")
    op.drop_index("ix_photos_observation_id", table_name="photos")
    op.drop_table("photos")
    op.drop_index("ix_observations_plant_observed_at", table_name="observations")
    op.drop_table("observations")
    op.drop_table("plants")
