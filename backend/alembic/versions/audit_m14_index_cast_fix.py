"""M14: Recreate partial index with explicit enum cast for type safety

Revision ID: audit_m14_index_cast
Revises: study_focus_001
Create Date: 2026-04-17
"""

from alembic import op

revision = "audit_m14_index_cast"
down_revision = "study_focus_001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # M14: Replace string-literal partial index with explicit enum cast.
    # The old index used WHERE status != 'archived' (implicit cast).
    # The new index casts to the enum type so the filter survives any rename.
    op.execute("DROP INDEX IF EXISTS scheduler.uq_daily_plans_active_per_user_date")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_daily_plans_active_per_user_date
        ON scheduler.daily_plans (user_id, plan_date)
        WHERE status != 'archived'::scheduler.plan_status
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS scheduler.uq_daily_plans_active_per_user_date")
    op.execute(
        """
        CREATE UNIQUE INDEX uq_daily_plans_active_per_user_date
        ON scheduler.daily_plans (user_id, plan_date)
        WHERE status != 'archived'
        """
    )
