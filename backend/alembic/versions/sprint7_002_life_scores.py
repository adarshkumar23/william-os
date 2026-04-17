"""Add intelligence life scores table

Revision ID: sprint7_intel_002
Revises: sprint7_intel_001
Create Date: 2026-04-06
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "sprint7_intel_002"
down_revision = "sprint7_intel_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "life_scores",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("score", sa.Float(), nullable=False),
        sa.Column("component_scores", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column(
            "computed_at",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_life_scores")),
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_life_scores_user_id"),
        "life_scores",
        ["user_id"],
        unique=False,
        schema="intelligence",
    )
    op.create_index(
        op.f("ix_intelligence_life_scores_computed_at"),
        "life_scores",
        ["computed_at"],
        unique=False,
        schema="intelligence",
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_intelligence_life_scores_computed_at"),
        table_name="life_scores",
        schema="intelligence",
    )
    op.drop_index(
        op.f("ix_intelligence_life_scores_user_id"),
        table_name="life_scores",
        schema="intelligence",
    )
    op.drop_table("life_scores", schema="intelligence")
