"""Add optional care intervals to plant profiles."""

import sqlalchemy as sa
from alembic import op

revision = "0006_care_intervals"
down_revision = "0005_environment_alerts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for column in ("watering_days", "feeding_days"):
        op.add_column("plants", sa.Column(column, sa.Integer(), nullable=True))
        op.create_check_constraint(f"ck_plants_{column}", "plants", f"{column} BETWEEN 1 AND 365")


def downgrade() -> None:
    for column in ("feeding_days", "watering_days"):
        op.drop_constraint(f"ck_plants_{column}", "plants", type_="check")
        op.drop_column("plants", column)
