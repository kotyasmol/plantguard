"""Add password credentials for repeat sign-in.

Revision ID: 0004_user_passwords
Revises: 0003_transactional_outbox
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_user_passwords"
down_revision: str | None = "0003_transactional_outbox"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Nullable preserves profiles created before password-based sign-in existed.
    # Their current bearer tokens remain valid.
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
