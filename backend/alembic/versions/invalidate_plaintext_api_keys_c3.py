"""invalidate plaintext api keys c3

Revision ID: invalidate_plaintext_api_keys_c3
Revises: audit_m14_index_cast
Create Date: 2026-04-17

Deactivates any API keys that were stored before the secure hashed-key
migration (C3 audit finding) so they cannot be used to authenticate.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'invalidate_plaintext_api_keys_c3'
down_revision: str | None = 'audit_m14_index_cast'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        sa.text(
            "UPDATE auth.api_keys SET is_active = false "
            "WHERE key_hash IS NULL OR key_hash = ''"
        )
    )


def downgrade() -> None:
    pass
