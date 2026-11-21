"""Add the transactional outbox.

Revision ID: 0003_transactional_outbox
Revises: 0002_users_and_ownership
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_transactional_outbox"
down_revision: str | None = "0002_users_and_ownership"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "outbox_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic", sa.String(length=160), nullable=False),
        sa.Column("message_key", sa.String(length=160), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column(
            "available_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("attempts >= 0", name="ck_outbox_events_attempts_nonnegative"),
        sa.CheckConstraint(
            "status IN ('pending', 'published')", name="ck_outbox_events_status"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbox_events"),
    )
    op.create_index(
        "ix_outbox_events_pending", "outbox_events", ["status", "available_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_outbox_events_pending", table_name="outbox_events")
    op.drop_table("outbox_events")
