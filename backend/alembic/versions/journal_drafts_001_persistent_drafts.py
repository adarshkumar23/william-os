"""Add persistent encrypted journal drafts table.

Revision ID: journal_drafts_001
Revises: integrations_001
Create Date: 2026-04-16
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "journal_drafts_001"
down_revision = "integrations_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    mood_enum = postgresql.ENUM(
        "great",
        "good",
        "okay",
        "low",
        "bad",
        name="journalmood",
        schema="journal",
        create_type=False,
    )

    op.create_table(
        "journal_drafts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("encrypted_content", sa.LargeBinary(), nullable=False),
        sa.Column("mood", mood_enum, nullable=True),
        sa.Column(
            "tags",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_journal_drafts")),
        sa.UniqueConstraint("user_id", name="uq_journal_drafts_user_id"),
        schema="journal",
    )
    op.create_index(
        op.f("ix_journal_journal_drafts_user_id"),
        "journal_drafts",
        ["user_id"],
        unique=False,
        schema="journal",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_journal_journal_drafts_user_id"),
        table_name="journal_drafts",
        schema="journal",
    )
    op.drop_table("journal_drafts", schema="journal")
