"""Add avatar_url to auth.users.

Revision ID: multiuser_001
Revises: onboarding_001
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "multiuser_001"
down_revision = "onboarding_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("avatar_url", sa.String(length=500), nullable=True),
        schema="auth",
    )


def downgrade() -> None:
    op.drop_column("users", "avatar_url", schema="auth")
