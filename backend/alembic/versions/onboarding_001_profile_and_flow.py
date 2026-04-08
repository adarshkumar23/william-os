"""Add onboarding profile fields and wake_time nullability.

Revision ID: onboarding_001
Revises: calendar_001
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "onboarding_001"
down_revision = "calendar_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("display_name", sa.String(length=100), nullable=True),
        schema="auth",
    )
    op.alter_column(
        "users",
        "wake_time",
        existing_type=sa.String(length=5),
        nullable=True,
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column("sleep_goal", sa.Float(), nullable=True),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column(
            "focus_areas",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column(
            "onboarding_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        schema="auth",
    )


def downgrade() -> None:
    op.execute("UPDATE auth.users SET wake_time = '06:00' WHERE wake_time IS NULL")
    op.alter_column(
        "users",
        "wake_time",
        existing_type=sa.String(length=5),
        nullable=False,
        schema="auth",
    )
    op.drop_column("users", "onboarding_completed", schema="auth")
    op.drop_column("users", "focus_areas", schema="auth")
    op.drop_column("users", "sleep_goal", schema="auth")
    op.drop_column("users", "display_name", schema="auth")
