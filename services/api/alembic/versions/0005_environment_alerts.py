"""Store manual environment readings and plant alerts.

Revision ID: 0005_environment_alerts
Revises: 0004_user_passwords
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_environment_alerts"
down_revision: str | None = "0004_user_passwords"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "environment_readings",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("humidity_pct", sa.Numeric(5, 2), nullable=True),
        sa.Column("temperature_c", sa.Numeric(5, 2), nullable=True),
        sa.Column(
            "occurred_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "humidity_pct IS NOT NULL OR temperature_c IS NOT NULL",
            name="ck_environment_readings_has_measurement",
        ),
        sa.CheckConstraint(
            "humidity_pct BETWEEN 0 AND 100", name="ck_environment_readings_humidity_range"
        ),
        sa.CheckConstraint(
            "temperature_c BETWEEN -50 AND 70",
            name="ck_environment_readings_temperature_range",
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name="fk_environment_readings_plant_id",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_environment_readings"),
    )
    op.create_index(
        "ix_environment_readings_plant_occurred_at",
        "environment_readings",
        ["plant_id", "occurred_at"],
    )
    op.create_table(
        "plant_alerts",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("plant_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Text(), nullable=False),
        sa.Column("alert_code", sa.String(24), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "alert_code IN ('humidity_too_low', 'humidity_too_high', "
            "'temperature_too_low', 'temperature_too_high')",
            name="ck_plant_alerts_alert_code",
        ),
        sa.CheckConstraint(
            "severity IN ('warning', 'critical')", name="ck_plant_alerts_severity"
        ),
        sa.ForeignKeyConstraint(
            ["plant_id"], ["plants.id"], name="fk_plant_alerts_plant_id", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_plant_alerts"),
        sa.UniqueConstraint("event_id", name="uq_plant_alerts_event_id"),
    )
    op.create_index(
        "ix_plant_alerts_plant_occurred_at", "plant_alerts", ["plant_id", "occurred_at"]
    )


def downgrade() -> None:
    op.drop_table("plant_alerts")
    op.drop_table("environment_readings")
