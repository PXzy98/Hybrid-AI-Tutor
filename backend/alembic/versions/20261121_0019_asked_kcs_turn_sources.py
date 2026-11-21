"""asked KC codes in the request log, sources and model of stored tutor turns (v5 V22)

Revision ID: 0019
Revises: 0018
Create Date: 2026-11-21 18:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0019'
down_revision: str | None = '0018'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('request_log', sa.Column('kc_ids', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('session_turn', sa.Column('sources', sa.JSON(), nullable=False, server_default='[]'))
    op.add_column('session_turn', sa.Column('target', sa.String(), nullable=True))
    op.add_column('session_turn', sa.Column('cut_off', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('session_turn', 'cut_off')
    op.drop_column('session_turn', 'target')
    op.drop_column('session_turn', 'sources')
    op.drop_column('request_log', 'kc_ids')
