"""Add intelligence schema, signals table, and cross-module rules table

Revision ID: sprint7_intel_001
Revises: william_b2_001
Create Date: 2026-04-06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "sprint7_intel_001"
down_revision = "william_b2_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS intelligence")

    op.create_table(
        "module_signals",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_module", sa.String(length=50), nullable=False),
        sa.Column("signal_type", sa.String(length=20), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "recorded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_module_signals")),
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_module_signals_user_id"),
        "module_signals",
        ["user_id"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_module_signals_source_module"),
        "module_signals",
        ["source_module"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_module_signals_signal_type"),
        "module_signals",
        ["signal_type"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_module_signals_recorded_at"),
        "module_signals",
        ["recorded_at"],
        unique=False,
        schema="intelligence",
    )

    op.create_table(
        "cross_module_rules",
        sa.Column("trigger_module", sa.String(length=50), nullable=False),
        sa.Column("trigger_condition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("affected_module", sa.String(length=50), nullable=False),
        sa.Column("adjustment_type", sa.String(length=50), nullable=False),
        sa.Column("adjustment_value", sa.Float(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_cross_module_rules")),
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_cross_module_rules_trigger_module"),
        "cross_module_rules",
        ["trigger_module"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_cross_module_rules_affected_module"),
        "cross_module_rules",
        ["affected_module"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_cross_module_rules_is_active"),
        "cross_module_rules",
        ["is_active"],
        unique=False,
        schema="intelligence",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_intelligence_cross_module_rules_is_active"),
        table_name="cross_module_rules",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_cross_module_rules_affected_module"),
        table_name="cross_module_rules",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_cross_module_rules_trigger_module"),
        table_name="cross_module_rules",
        schema="intelligence",
    )
    op.drop_table("cross_module_rules", schema="intelligence")

    op.drop_index(
        op.f("ix_intelligence_module_signals_recorded_at"),
        table_name="module_signals",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_module_signals_signal_type"),
        table_name="module_signals",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_module_signals_source_module"),
        table_name="module_signals",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_module_signals_user_id"),
        table_name="module_signals",
        schema="intelligence",
    )
    op.drop_table("module_signals", schema="intelligence")
