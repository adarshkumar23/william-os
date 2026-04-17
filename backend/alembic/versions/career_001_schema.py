"""career: add career schema and 6 tables

Revision ID: career_001
Revises: sprint10_001
Create Date: 2026-04-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "career_001"
down_revision: tuple[str, str] | None = ("sprint10_001", "audit_m14_index_cast")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS career")

    # ── problems ────────────────────────────────────────────────────
    op.create_table(
        "problems",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("platform", sa.String(length=32), nullable=True),
        sa.Column("external_id", sa.String(length=128), nullable=True),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("difficulty", sa.String(length=16), nullable=True),
        sa.Column("topics", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("solved_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("time_spent_minutes", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_problems")),
        sa.UniqueConstraint("user_id", "platform", "external_id", name="uq_problems_user_platform_ext"),
        schema="career",
    )
    op.create_index(
        "ix_career_problems_user_id", "problems", ["user_id"], unique=False, schema="career"
    )
    op.create_index(
        "ix_career_problems_user_solved_at",
        "problems",
        ["user_id", "solved_at"],
        unique=False,
        schema="career",
    )
    op.create_index(
        "ix_career_problems_topics_gin",
        "problems",
        ["topics"],
        unique=False,
        schema="career",
        postgresql_using="gin",
    )

    # ── projects ────────────────────────────────────────────────────
    op.create_table(
        "projects",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("tech_stack", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="planning"),
        sa.Column("live_url", sa.Text(), nullable=True),
        sa.Column("github_url", sa.Text(), nullable=True),
        sa.Column("on_resume", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("started_at", sa.Date(), nullable=True),
        sa.Column("shipped_at", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_projects")),
        schema="career",
    )
    op.create_index(
        "ix_career_projects_user_id", "projects", ["user_id"], unique=False, schema="career"
    )
    op.create_index(
        "ix_career_projects_tech_stack_gin",
        "projects",
        ["tech_stack"],
        unique=False,
        schema="career",
        postgresql_using="gin",
    )

    # ── applications ────────────────────────────────────────────────
    op.create_table(
        "applications",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("company", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=128), nullable=False),
        sa.Column("platform", sa.String(length=64), nullable=True),
        sa.Column("stage", sa.String(length=32), nullable=False, server_default="researching"),
        sa.Column("stage_updated_at", sa.DateTime(timezone=False), nullable=True),
        sa.Column("applied_at", sa.Date(), nullable=True),
        sa.Column("next_action", sa.Text(), nullable=True),
        sa.Column("next_action_due", sa.Date(), nullable=True),
        sa.Column("stipend_or_ctc", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applications")),
        schema="career",
    )
    op.create_index(
        "ix_career_applications_user_id", "applications", ["user_id"], unique=False, schema="career"
    )
    op.create_index(
        "ix_career_applications_active_stage",
        "applications",
        ["user_id", "stage"],
        unique=False,
        schema="career",
        postgresql_where=sa.text("archived = false"),
    )

    # ── contacts ────────────────────────────────────────────────────
    op.create_table(
        "contacts",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("company", sa.String(length=128), nullable=True),
        sa.Column("role", sa.String(length=128), nullable=True),
        sa.Column("tags", postgresql.ARRAY(sa.Text()), nullable=False, server_default="{}"),
        sa.Column("linkedin_url", sa.Text(), nullable=True),
        sa.Column("email", sa.String(length=256), nullable=True),
        sa.Column("temperature", sa.String(length=16), nullable=False, server_default="cold"),
        sa.Column("last_contacted_at", sa.Date(), nullable=True),
        sa.Column("next_followup_at", sa.Date(), nullable=True),
        sa.Column("relationship_notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_contacts")),
        schema="career",
    )
    op.create_index(
        "ix_career_contacts_user_id", "contacts", ["user_id"], unique=False, schema="career"
    )
    op.create_index(
        "ix_career_contacts_followup",
        "contacts",
        ["user_id", "next_followup_at"],
        unique=False,
        schema="career",
        postgresql_where=sa.text("next_followup_at IS NOT NULL"),
    )
    op.create_index(
        "ix_career_contacts_tags_gin",
        "contacts",
        ["tags"],
        unique=False,
        schema="career",
        postgresql_using="gin",
    )

    # ── opportunities ───────────────────────────────────────────────
    op.create_table(
        "opportunities",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("source", sa.String(length=64), nullable=True),
        sa.Column("kind", sa.String(length=32), nullable=False, server_default="other"),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("deadline", sa.DateTime(timezone=False), nullable=True),
        sa.Column("stipend_info", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="inbox"),
        sa.Column("converted_to_application_id", sa.UUID(), nullable=True),
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
        sa.ForeignKeyConstraint(
            ["converted_to_application_id"], ["career.applications.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_opportunities")),
        schema="career",
    )
    op.create_index(
        "ix_career_opportunities_user_id", "opportunities", ["user_id"], unique=False, schema="career"
    )
    op.create_index(
        "ix_career_opportunities_inbox_deadline",
        "opportunities",
        ["user_id", "deadline"],
        unique=False,
        schema="career",
        postgresql_where=sa.text("status = 'inbox'"),
    )

    # ── score_snapshots ─────────────────────────────────────────────
    op.create_table(
        "score_snapshots",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False),
        sa.Column("overall_score", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "components",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
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
        sa.PrimaryKeyConstraint("id", name=op.f("pk_score_snapshots")),
        sa.UniqueConstraint("user_id", "snapshot_date", name="uq_score_snapshots_user_date"),
        schema="career",
    )
    op.create_index(
        "ix_career_score_snapshots_user_id",
        "score_snapshots",
        ["user_id"],
        unique=False,
        schema="career",
    )


def downgrade() -> None:
    op.drop_table("score_snapshots", schema="career")
    op.drop_table("opportunities", schema="career")
    op.drop_table("contacts", schema="career")
    op.drop_table("applications", schema="career")
    op.drop_table("projects", schema="career")
    op.drop_table("problems", schema="career")
    op.execute("DROP SCHEMA IF EXISTS career CASCADE")
