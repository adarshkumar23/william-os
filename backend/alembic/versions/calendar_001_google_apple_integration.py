"""Add calendar integration tables for Google and Apple connectors.

Revision ID: calendar_001
Revises: sprint10_001
Create Date: 2026-04-07
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "calendar_001"
down_revision = "sprint10_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS calendar")

    op.create_table(
        "google_tokens",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("access_token", sa.Text(), nullable=False),
        sa.Column("refresh_token", sa.Text(), nullable=True),
        sa.Column("token_expiry", sa.DateTime(timezone=False), nullable=True),
        sa.Column("scope", sa.Text(), nullable=True),
        sa.Column("token_type", sa.String(length=50), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_google_tokens")),
        sa.UniqueConstraint("user_id", name="uq_calendar_google_tokens_user_id"),
        schema="calendar",
    )
    op.create_index(
        op.f("ix_calendar_google_tokens_user_id"),
        "google_tokens",
        ["user_id"],
        unique=False,
        schema="calendar",
    )

    op.create_table(
        "apple_credentials",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("apple_id_encrypted", sa.Text(), nullable=False),
        sa.Column("app_password_encrypted", sa.Text(), nullable=False),
        sa.Column("caldav_url", sa.String(length=255), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_apple_credentials")),
        sa.UniqueConstraint("user_id", name="uq_calendar_apple_credentials_user_id"),
        schema="calendar",
    )
    op.create_index(
        op.f("ix_calendar_apple_credentials_user_id"),
        "apple_credentials",
        ["user_id"],
        unique=False,
        schema="calendar",
    )

    op.create_table(
        "cached_events",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("event_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=False), nullable=False),
        sa.Column("location", sa.String(length=500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("last_synced", sa.DateTime(timezone=False), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cached_events")),
        schema="calendar",
    )
    op.create_index(
        op.f("ix_calendar_cached_events_source"),
        "cached_events",
        ["source"],
        unique=False,
        schema="calendar",
    )
    op.create_index(
        op.f("ix_calendar_cached_events_start_time"),
        "cached_events",
        ["start_time"],
        unique=False,
        schema="calendar",
    )
    op.create_index(
        op.f("ix_calendar_cached_events_user_id"),
        "cached_events",
        ["user_id"],
        unique=False,
        schema="calendar",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_calendar_cached_events_user_id"), table_name="cached_events", schema="calendar"
    )
    op.drop_index(
        op.f("ix_calendar_cached_events_start_time"), table_name="cached_events", schema="calendar"
    )
    op.drop_index(
        op.f("ix_calendar_cached_events_source"), table_name="cached_events", schema="calendar"
    )
    op.drop_table("cached_events", schema="calendar")

    op.drop_index(
        op.f("ix_calendar_apple_credentials_user_id"),
        table_name="apple_credentials",
        schema="calendar",
    )
    op.drop_table("apple_credentials", schema="calendar")

    op.drop_index(
        op.f("ix_calendar_google_tokens_user_id"), table_name="google_tokens", schema="calendar"
    )
    op.drop_table("google_tokens", schema="calendar")
