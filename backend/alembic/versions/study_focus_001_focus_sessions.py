"""Add study focus sessions table.

Revision ID: study_focus_001
Revises: webhooks_001
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "study_focus_001"
down_revision = "webhooks_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "focus_sessions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("subject_id", sa.UUID(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("planned_minutes", sa.Integer(), server_default=sa.text("25"), nullable=False),
        sa.Column("actual_minutes", sa.Integer(), nullable=True),
        sa.Column("distraction_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("focus_score", sa.Float(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'active'"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["subject_id"], ["study.subjects.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_focus_sessions")),
        schema="study",
    )
    op.create_index(
        op.f("ix_study_focus_sessions_user_id"),
        "focus_sessions",
        ["user_id"],
        unique=False,
        schema="study",
    )
    op.create_index(
        op.f("ix_study_focus_sessions_subject_id"),
        "focus_sessions",
        ["subject_id"],
        unique=False,
        schema="study",
    )
    op.create_index(
        op.f("ix_study_focus_sessions_started_at"),
        "focus_sessions",
        ["started_at"],
        unique=False,
        schema="study",
    )
    op.create_index(
        op.f("ix_study_focus_sessions_status"),
        "focus_sessions",
        ["status"],
        unique=False,
        schema="study",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_study_focus_sessions_status"),
        table_name="focus_sessions",
        schema="study",
    )
    op.drop_index(
        op.f("ix_study_focus_sessions_started_at"),
        table_name="focus_sessions",
        schema="study",
    )
    op.drop_index(
        op.f("ix_study_focus_sessions_subject_id"),
        table_name="focus_sessions",
        schema="study",
    )
    op.drop_index(
        op.f("ix_study_focus_sessions_user_id"),
        table_name="focus_sessions",
        schema="study",
    )
    op.drop_table("focus_sessions", schema="study")
