"""Add users and plant ownership.

Revision ID: 0002_users_and_ownership
Revises: 0001_initial_domain
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_users_and_ownership"
down_revision: str | None = "0001_initial_domain"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

LEGACY_USER_ID = "00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column(
            "id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), nullable=False
        ),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("token_hash", name="uq_users_token_hash"),
    )
    op.add_column("plants", sa.Column("owner_id", sa.Uuid(), nullable=True))
    op.execute(
        sa.text(
            "INSERT INTO users (id, email, display_name, token_hash) "
            "VALUES (CAST(:id AS UUID), 'legacy-import@plantguard.invalid', "
            "'Imported data', :token_hash)"
        ).bindparams(id=LEGACY_USER_ID, token_hash="0" * 64)
    )
    op.execute(
        sa.text(
            "UPDATE plants SET owner_id = CAST(:owner_id AS UUID) WHERE owner_id IS NULL"
        ).bindparams(owner_id=LEGACY_USER_ID)
    )
    op.alter_column("plants", "owner_id", nullable=False)
    op.create_foreign_key(
        "fk_plants_owner_id", "plants", "users", ["owner_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_plants_owner_id", "plants", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_plants_owner_id", table_name="plants")
    op.drop_constraint("fk_plants_owner_id", "plants", type_="foreignkey")
    op.drop_column("plants", "owner_id")
    op.drop_table("users")
