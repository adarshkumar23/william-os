"""Add webhook registry and delivery tables for rules module.

Revision ID: webhooks_001
Revises: journal_drafts_001
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "webhooks_001"
down_revision = "journal_drafts_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_registrations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("event_type", sa.String(length=100), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("secret", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failure_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_registrations")),
        schema="rules",
    )
    op.create_index(
        op.f("ix_rules_webhook_registrations_event_type"),
        "webhook_registrations",
        ["event_type"],
        unique=False,
        schema="rules",
    )
    op.create_index(
        op.f("ix_rules_webhook_registrations_is_active"),
        "webhook_registrations",
        ["is_active"],
        unique=False,
        schema="rules",
    )
    op.create_index(
        op.f("ix_rules_webhook_registrations_user_id"),
        "webhook_registrations",
        ["user_id"],
        unique=False,
        schema="rules",
    )

    op.create_table(
        "webhook_deliveries",
        sa.Column("registration_id", sa.UUID(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("attempts", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["registration_id"], ["rules.webhook_registrations.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_webhook_deliveries")),
        schema="rules",
    )
    op.create_index(
        op.f("ix_rules_webhook_deliveries_registration_id"),
        "webhook_deliveries",
        ["registration_id"],
        unique=False,
        schema="rules",
    )
    op.create_index(
        op.f("ix_rules_webhook_deliveries_status"),
        "webhook_deliveries",
        ["status"],
        unique=False,
        schema="rules",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_rules_webhook_deliveries_status"),
        table_name="webhook_deliveries",
        schema="rules",
    )
    op.drop_index(
        op.f("ix_rules_webhook_deliveries_registration_id"),
        table_name="webhook_deliveries",
        schema="rules",
    )
    op.drop_table("webhook_deliveries", schema="rules")

    op.drop_index(
        op.f("ix_rules_webhook_registrations_user_id"),
        table_name="webhook_registrations",
        schema="rules",
    )
    op.drop_index(
        op.f("ix_rules_webhook_registrations_is_active"),
        table_name="webhook_registrations",
        schema="rules",
    )
    op.drop_index(
        op.f("ix_rules_webhook_registrations_event_type"),
        table_name="webhook_registrations",
        schema="rules",
    )
    op.drop_table("webhook_registrations", schema="rules")
