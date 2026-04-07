"""Add rules engine tables

Revision ID: sprint9_001
Revises: sprint8_001
Create Date: 2026-04-07
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "sprint9_001"
down_revision = "sprint8_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS rules")

    op.create_table(
        "user_rules",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("trigger_module", sa.String(length=50), nullable=False),
        sa.Column("trigger_condition", sa.JSON(), nullable=False),
        sa.Column("action_module", sa.String(length=50), nullable=False),
        sa.Column("action_type", sa.String(length=80), nullable=False),
        sa.Column("action_params", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_triggered", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_rules")),
        schema="rules",
    )
    op.create_index(op.f("ix_rules_user_rules_user_id"), "user_rules", ["user_id"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_user_rules_trigger_module"), "user_rules", ["trigger_module"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_user_rules_action_module"), "user_rules", ["action_module"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_user_rules_action_type"), "user_rules", ["action_type"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_user_rules_is_active"), "user_rules", ["is_active"], unique=False, schema="rules")

    op.create_table(
        "rule_execution_logs",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("rule_id", sa.UUID(), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("action_success", sa.Boolean(), nullable=False),
        sa.Column("context_snapshot", sa.JSON(), nullable=False),
        sa.Column("action_result", sa.JSON(), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.user_rules.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["auth.users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_rule_execution_logs")),
        schema="rules",
    )
    op.create_index(op.f("ix_rules_rule_execution_logs_user_id"), "rule_execution_logs", ["user_id"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_rule_execution_logs_rule_id"), "rule_execution_logs", ["rule_id"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_rule_execution_logs_matched"), "rule_execution_logs", ["matched"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_rule_execution_logs_action_success"), "rule_execution_logs", ["action_success"], unique=False, schema="rules")
    op.create_index(op.f("ix_rules_rule_execution_logs_executed_at"), "rule_execution_logs", ["executed_at"], unique=False, schema="rules")


def downgrade() -> None:
    op.drop_index(op.f("ix_rules_rule_execution_logs_executed_at"), table_name="rule_execution_logs", schema="rules")
    op.drop_index(op.f("ix_rules_rule_execution_logs_action_success"), table_name="rule_execution_logs", schema="rules")
    op.drop_index(op.f("ix_rules_rule_execution_logs_matched"), table_name="rule_execution_logs", schema="rules")
    op.drop_index(op.f("ix_rules_rule_execution_logs_rule_id"), table_name="rule_execution_logs", schema="rules")
    op.drop_index(op.f("ix_rules_rule_execution_logs_user_id"), table_name="rule_execution_logs", schema="rules")
    op.drop_table("rule_execution_logs", schema="rules")

    op.drop_index(op.f("ix_rules_user_rules_is_active"), table_name="user_rules", schema="rules")
    op.drop_index(op.f("ix_rules_user_rules_action_type"), table_name="user_rules", schema="rules")
    op.drop_index(op.f("ix_rules_user_rules_action_module"), table_name="user_rules", schema="rules")
    op.drop_index(op.f("ix_rules_user_rules_trigger_module"), table_name="user_rules", schema="rules")
    op.drop_index(op.f("ix_rules_user_rules_user_id"), table_name="user_rules", schema="rules")
    op.drop_table("user_rules", schema="rules")
