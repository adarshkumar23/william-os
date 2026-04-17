"""merge career_001 and invalidate_plaintext_api_keys_c3

Revision ID: merge_career_and_c3_001
Revises: career_001, invalidate_plaintext_api_keys_c3
Create Date: 2026-04-18

"""
from collections.abc import Sequence

revision: str = 'merge_career_and_c3_001'
down_revision: tuple[str, str] = ('career_001', 'invalidate_plaintext_api_keys_c3')
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
