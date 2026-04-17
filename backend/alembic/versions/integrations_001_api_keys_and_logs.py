"""Add integrations API keys and integration logs tables.

Revision ID: integrations_001
Revises: multiuser_001
Create Date: 2026-04-08
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "integrations_001"
down_revision = "multiuser_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS integrations")

    op.create_table(
        "api_keys",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_keys")),
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_api_keys_is_active"),
        "api_keys",
        ["is_active"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_api_keys_key_hash"),
        "api_keys",
        ["key_hash"],
        unique=True,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_api_keys_key_prefix"),
        "api_keys",
        ["key_prefix"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_api_keys_user_id"),
        "api_keys",
        ["user_id"],
        unique=False,
        schema="auth",
    )

    op.create_table(
        "integration_logs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("endpoint", sa.String(length=100), nullable=False),
        sa.Column("source", sa.String(length=50), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("success", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_integration_logs")),
        schema="integrations",
    )
    op.create_index(
        op.f("ix_integrations_integration_logs_processed_at"),
        "integration_logs",
        ["processed_at"],
        unique=False,
        schema="integrations",
    )
    op.create_index(
        op.f("ix_integrations_integration_logs_user_id"),
        "integration_logs",
        ["user_id"],
        unique=False,
        schema="integrations",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_integrations_integration_logs_user_id"),
        table_name="integration_logs",
        schema="integrations",
    )
    op.drop_index(
        op.f("ix_integrations_integration_logs_processed_at"),
        table_name="integration_logs",
        schema="integrations",
    )
    op.drop_table("integration_logs", schema="integrations")
    op.execute("DROP SCHEMA IF EXISTS integrations")

    op.drop_index(op.f("ix_auth_api_keys_user_id"), table_name="api_keys", schema="auth")
    op.drop_index(op.f("ix_auth_api_keys_key_prefix"), table_name="api_keys", schema="auth")
    op.drop_index(op.f("ix_auth_api_keys_key_hash"), table_name="api_keys", schema="auth")
    op.drop_index(op.f("ix_auth_api_keys_is_active"), table_name="api_keys", schema="auth")
    op.drop_table("api_keys", schema="auth")
