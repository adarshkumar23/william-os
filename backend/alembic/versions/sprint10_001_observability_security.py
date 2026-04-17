"""Add sprint 10 security and observability related tables

Revision ID: sprint10_001
Revises: sprint9_001
Create Date: 2026-04-07
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "sprint10_001"
down_revision = "sprint9_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS security")

    op.add_column(
        "users",
        sa.Column("totp_enabled", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        schema="auth",
    )
    op.add_column(
        "users",
        sa.Column(
            "permission_scopes", sa.JSON(), server_default=sa.text("'[]'::json"), nullable=False
        ),
        schema="auth",
    )

    op.create_table(
        "login_history",
        sa.Column("user_id", sa.UUID(), nullable=True),
        sa.Column("ip", sa.String(length=64), nullable=True),
        sa.Column("country", sa.String(length=80), nullable=True),
        sa.Column("device_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
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
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_login_history")),
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_login_history_user_id"),
        "login_history",
        ["user_id"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_login_history_success"),
        "login_history",
        ["success"],
        unique=False,
        schema="auth",
    )
    op.create_index(
        op.f("ix_auth_login_history_timestamp"),
        "login_history",
        ["timestamp"],
        unique=False,
        schema="auth",
    )

    op.create_table(
        "api_secrets",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("key_ciphertext", sa.Text(), nullable=False),
        sa.Column("key_hint", sa.String(length=16), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_api_secrets")),
        schema="security",
    )
    op.create_index(
        op.f("ix_security_api_secrets_user_id"),
        "api_secrets",
        ["user_id"],
        unique=False,
        schema="security",
    )
    op.create_index(
        op.f("ix_security_api_secrets_provider"),
        "api_secrets",
        ["provider"],
        unique=False,
        schema="security",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_security_api_secrets_provider"), table_name="api_secrets", schema="security"
    )
    op.drop_index(
        op.f("ix_security_api_secrets_user_id"), table_name="api_secrets", schema="security"
    )
    op.drop_table("api_secrets", schema="security")

    op.drop_index(
        op.f("ix_auth_login_history_timestamp"), table_name="login_history", schema="auth"
    )
    op.drop_index(op.f("ix_auth_login_history_success"), table_name="login_history", schema="auth")
    op.drop_index(op.f("ix_auth_login_history_user_id"), table_name="login_history", schema="auth")
    op.drop_table("login_history", schema="auth")

    op.drop_column("users", "permission_scopes", schema="auth")
    op.drop_column("users", "totp_enabled", schema="auth")
