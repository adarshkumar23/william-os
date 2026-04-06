"""Add unique constraints and composite indexes to prevent race conditions

Revision ID: william_b2_001
Revises: 436dfab1ec67
Create Date: 2026-04-07
"""

from alembic import op

revision = "william_b2_001"
down_revision = "436dfab1ec67"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Prevent duplicate habit check-ins for the same habit on the same day.
    # Without this, two concurrent POST /{id}/check-in requests both see
    # no existing row and insert two rows, corrupting streak counts.
    op.create_unique_constraint(
        "uq_habit_check_ins_habit_date",
        "habit_check_ins",
        ["habit_id", "check_date"],
        schema="habits",
    )

    # Prevent duplicate medicine dose logs for the same slot.
    op.create_unique_constraint(
        "uq_medicine_log_slot",
        "medicine_logs",
        ["medicine_id", "log_date", "scheduled_time"],
        schema="medicine",
    )

    # Partial unique index: only one non-archived plan per user per day.
    # This prevents the schedule generation race condition where two
    # concurrent requests both create an ACTIVE plan for the same date.
    op.execute(
        """
        CREATE UNIQUE INDEX uq_daily_plans_active_per_user_date
        ON scheduler.daily_plans (user_id, plan_date)
        WHERE status != 'archived'
        """
    )

    # Composite index for the hot-path scheduler query
    # (_get_plan filters on user_id + plan_date + status != ARCHIVED).
    op.create_index(
        "ix_daily_plans_user_date_status",
        "daily_plans",
        ["user_id", "plan_date", "status"],
        schema="scheduler",
    )

    # Composite index for trade history queries.
    op.create_index(
        "ix_trade_logs_user_date",
        "trade_logs",
        ["user_id", "trade_date"],
        schema="trading",
    )


def downgrade() -> None:
    op.drop_index("ix_trade_logs_user_date", table_name="trade_logs", schema="trading")
    op.drop_index("ix_daily_plans_user_date_status", table_name="daily_plans", schema="scheduler")
    op.execute("DROP INDEX IF EXISTS scheduler.uq_daily_plans_active_per_user_date")
    op.drop_constraint("uq_medicine_log_slot", "medicine_logs", schema="medicine")
    op.drop_constraint("uq_habit_check_ins_habit_date", "habit_check_ins", schema="habits")
