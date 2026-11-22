"""fixed notes of stored tutor turns (v5 V22 N6)

Revision ID: 0020
Revises: 0019
Create Date: 2026-11-22 10:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0020'
down_revision: str | None = '0019'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('session_turn', sa.Column('notes', sa.JSON(), nullable=False, server_default='[]'))


def downgrade() -> None:
    op.drop_column('session_turn', 'notes')
