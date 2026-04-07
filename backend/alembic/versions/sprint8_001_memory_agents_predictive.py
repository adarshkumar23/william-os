"""Add memory graph, agent layer, and predictive warnings tables

Revision ID: sprint8_001
Revises: sprint7_intel_003
Create Date: 2026-04-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "sprint8_001"
down_revision = "sprint7_intel_003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS memory")
    op.execute("CREATE SCHEMA IF NOT EXISTS agents")

    op.execute("CREATE TYPE memory.memorytype AS ENUM ('preference', 'pattern', 'correlation', 'insight')")

    op.create_table(
        "user_memories",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("memory_type", sa.Enum("preference", "pattern", "correlation", "insight", name="memorytype", schema="memory"), nullable=False),
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("last_updated", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("source_modules", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_memories")),
        sa.UniqueConstraint("user_id", "key", name="uq_user_memories_user_key"),
        schema="memory",
    )
    op.create_index(op.f("ix_memory_user_memories_user_id"), "user_memories", ["user_id"], unique=False, schema="memory")
    op.create_index(op.f("ix_memory_user_memories_memory_type"), "user_memories", ["memory_type"], unique=False, schema="memory")
    op.create_index(op.f("ix_memory_user_memories_last_updated"), "user_memories", ["last_updated"], unique=False, schema="memory")

    op.create_table(
        "memory_insights",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("insight", sa.Text(), nullable=False),
        sa.Column("supporting_evidence", sa.JSON(), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_memory_insights")),
        schema="memory",
    )
    op.create_index(op.f("ix_memory_memory_insights_user_id"), "memory_insights", ["user_id"], unique=False, schema="memory")
    op.create_index(op.f("ix_memory_memory_insights_generated_at"), "memory_insights", ["generated_at"], unique=False, schema="memory")
    op.create_index(op.f("ix_memory_memory_insights_is_active"), "memory_insights", ["is_active"], unique=False, schema="memory")

    op.create_table(
        "agent_status",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("last_recommendation", sa.JSON(), nullable=False),
        sa.Column("last_action", sa.JSON(), nullable=False),
        sa.Column("last_run_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_status")),
        sa.UniqueConstraint("user_id", "agent_name", name="uq_agent_status_user_name"),
        schema="agents",
    )
    op.create_index(op.f("ix_agents_agent_status_user_id"), "agent_status", ["user_id"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_status_agent_name"), "agent_status", ["agent_name"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_status_status"), "agent_status", ["status"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_status_last_run_at"), "agent_status", ["last_run_at"], unique=False, schema="agents")

    op.create_table(
        "agent_recommendations",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("urgency", sa.Integer(), nullable=False),
        sa.Column("recommendation", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_recommendations")),
        schema="agents",
    )
    op.create_index(op.f("ix_agents_agent_recommendations_user_id"), "agent_recommendations", ["user_id"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_recommendations_agent_name"), "agent_recommendations", ["agent_name"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_recommendations_urgency"), "agent_recommendations", ["urgency"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_recommendations_severity"), "agent_recommendations", ["severity"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_recommendations_status"), "agent_recommendations", ["status"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_recommendations_is_active"), "agent_recommendations", ["is_active"], unique=False, schema="agents")

    op.create_table(
        "agent_actions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("action_type", sa.String(length=50), nullable=False),
        sa.Column("action_payload", sa.JSON(), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_actions")),
        schema="agents",
    )
    op.create_index(op.f("ix_agents_agent_actions_user_id"), "agent_actions", ["user_id"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_actions_agent_name"), "agent_actions", ["agent_name"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_actions_action_type"), "agent_actions", ["action_type"], unique=False, schema="agents")
    op.create_index(op.f("ix_agents_agent_actions_executed_at"), "agent_actions", ["executed_at"], unique=False, schema="agents")

    op.create_table(
        "predictive_warnings",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("warning_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("explanation", sa.Text(), nullable=False),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("detected_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_predictive_warnings")),
        schema="intelligence",
    )
    op.create_index(op.f("ix_intelligence_predictive_warnings_user_id"), "predictive_warnings", ["user_id"], unique=False, schema="intelligence")
    op.create_index(op.f("ix_intelligence_predictive_warnings_warning_type"), "predictive_warnings", ["warning_type"], unique=False, schema="intelligence")
    op.create_index(op.f("ix_intelligence_predictive_warnings_severity"), "predictive_warnings", ["severity"], unique=False, schema="intelligence")
    op.create_index(op.f("ix_intelligence_predictive_warnings_is_active"), "predictive_warnings", ["is_active"], unique=False, schema="intelligence")
    op.create_index(op.f("ix_intelligence_predictive_warnings_detected_at"), "predictive_warnings", ["detected_at"], unique=False, schema="intelligence")


def downgrade() -> None:
    op.drop_index(op.f("ix_intelligence_predictive_warnings_detected_at"), table_name="predictive_warnings", schema="intelligence")
    op.drop_index(op.f("ix_intelligence_predictive_warnings_is_active"), table_name="predictive_warnings", schema="intelligence")
    op.drop_index(op.f("ix_intelligence_predictive_warnings_severity"), table_name="predictive_warnings", schema="intelligence")
    op.drop_index(op.f("ix_intelligence_predictive_warnings_warning_type"), table_name="predictive_warnings", schema="intelligence")
    op.drop_index(op.f("ix_intelligence_predictive_warnings_user_id"), table_name="predictive_warnings", schema="intelligence")
    op.drop_table("predictive_warnings", schema="intelligence")

    op.drop_index(op.f("ix_agents_agent_actions_executed_at"), table_name="agent_actions", schema="agents")
    op.drop_index(op.f("ix_agents_agent_actions_action_type"), table_name="agent_actions", schema="agents")
    op.drop_index(op.f("ix_agents_agent_actions_agent_name"), table_name="agent_actions", schema="agents")
    op.drop_index(op.f("ix_agents_agent_actions_user_id"), table_name="agent_actions", schema="agents")
    op.drop_table("agent_actions", schema="agents")

    op.drop_index(op.f("ix_agents_agent_recommendations_is_active"), table_name="agent_recommendations", schema="agents")
    op.drop_index(op.f("ix_agents_agent_recommendations_status"), table_name="agent_recommendations", schema="agents")
    op.drop_index(op.f("ix_agents_agent_recommendations_severity"), table_name="agent_recommendations", schema="agents")
    op.drop_index(op.f("ix_agents_agent_recommendations_urgency"), table_name="agent_recommendations", schema="agents")
    op.drop_index(op.f("ix_agents_agent_recommendations_agent_name"), table_name="agent_recommendations", schema="agents")
    op.drop_index(op.f("ix_agents_agent_recommendations_user_id"), table_name="agent_recommendations", schema="agents")
    op.drop_table("agent_recommendations", schema="agents")

    op.drop_index(op.f("ix_agents_agent_status_last_run_at"), table_name="agent_status", schema="agents")
    op.drop_index(op.f("ix_agents_agent_status_status"), table_name="agent_status", schema="agents")
    op.drop_index(op.f("ix_agents_agent_status_agent_name"), table_name="agent_status", schema="agents")
    op.drop_index(op.f("ix_agents_agent_status_user_id"), table_name="agent_status", schema="agents")
    op.drop_table("agent_status", schema="agents")

    op.drop_index(op.f("ix_memory_memory_insights_is_active"), table_name="memory_insights", schema="memory")
    op.drop_index(op.f("ix_memory_memory_insights_generated_at"), table_name="memory_insights", schema="memory")
    op.drop_index(op.f("ix_memory_memory_insights_user_id"), table_name="memory_insights", schema="memory")
    op.drop_table("memory_insights", schema="memory")

    op.drop_index(op.f("ix_memory_user_memories_last_updated"), table_name="user_memories", schema="memory")
    op.drop_index(op.f("ix_memory_user_memories_memory_type"), table_name="user_memories", schema="memory")
    op.drop_index(op.f("ix_memory_user_memories_user_id"), table_name="user_memories", schema="memory")
    op.drop_table("user_memories", schema="memory")

    op.execute("DROP TYPE memory.memorytype")
