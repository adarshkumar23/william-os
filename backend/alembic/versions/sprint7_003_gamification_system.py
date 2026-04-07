"""Add gamification schema and XP/momentum tables

Revision ID: sprint7_intel_003
Revises: sprint7_intel_002
Create Date: 2026-04-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "sprint7_intel_003"
down_revision = "sprint7_intel_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS gamification")

    op.create_table(
        "user_xp",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("total_xp", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column(
            "last_updated",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_xp")),
        sa.UniqueConstraint("user_id", name=op.f("uq_user_xp_user_id")),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_user_xp_user_id"),
        "user_xp",
        ["user_id"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_user_xp_last_updated"),
        "user_xp",
        ["last_updated"],
        unique=False,
        schema="gamification",
    )

    op.create_table(
        "xp_events",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("source_module", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("xp_earned", sa.Integer(), nullable=False),
        sa.Column(
            "earned_at",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xp_events")),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_xp_events_user_id"),
        "xp_events",
        ["user_id"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_xp_events_source_module"),
        "xp_events",
        ["source_module"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_xp_events_action"),
        "xp_events",
        ["action"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_xp_events_earned_at"),
        "xp_events",
        ["earned_at"],
        unique=False,
        schema="gamification",
    )

    op.create_table(
        "personal_records",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("record_type", sa.String(length=80), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column(
            "achieved_at",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_personal_records")),
        sa.UniqueConstraint(
            "user_id",
            "record_type",
            name="uq_personal_records_user_record_type",
        ),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_personal_records_user_id"),
        "personal_records",
        ["user_id"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_personal_records_record_type"),
        "personal_records",
        ["record_type"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_personal_records_achieved_at"),
        "personal_records",
        ["achieved_at"],
        unique=False,
        schema="gamification",
    )

    op.create_table(
        "weekly_momentum",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("week_start", sa.Date(), nullable=False),
        sa.Column("momentum_score", sa.Float(), nullable=False),
        sa.Column("discipline_debt", sa.Float(), nullable=False),
        sa.Column("focus_rank", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_weekly_momentum")),
        sa.UniqueConstraint("user_id", "week_start", name="uq_weekly_momentum_user_week"),
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_weekly_momentum_user_id"),
        "weekly_momentum",
        ["user_id"],
        unique=False,
        schema="gamification",
    )
    op.create_index(
        op.f("ix_gamification_weekly_momentum_week_start"),
        "weekly_momentum",
        ["week_start"],
        unique=False,
        schema="gamification",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_gamification_weekly_momentum_week_start"),
        table_name="weekly_momentum",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_weekly_momentum_user_id"),
        table_name="weekly_momentum",
        schema="gamification",
    )
    op.drop_table("weekly_momentum", schema="gamification")

    op.drop_index(
        op.f("ix_gamification_personal_records_achieved_at"),
        table_name="personal_records",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_personal_records_record_type"),
        table_name="personal_records",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_personal_records_user_id"),
        table_name="personal_records",
        schema="gamification",
    )
    op.drop_table("personal_records", schema="gamification")

    op.drop_index(
        op.f("ix_gamification_xp_events_earned_at"),
        table_name="xp_events",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_xp_events_action"),
        table_name="xp_events",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_xp_events_source_module"),
        table_name="xp_events",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_xp_events_user_id"),
        table_name="xp_events",
        schema="gamification",
    )
    op.drop_table("xp_events", schema="gamification")

    op.drop_index(
        op.f("ix_gamification_user_xp_last_updated"),
        table_name="user_xp",
        schema="gamification",
    )
    op.drop_index(
        op.f("ix_gamification_user_xp_user_id"),
        table_name="user_xp",
        schema="gamification",
    )
    op.drop_table("user_xp", schema="gamification")
