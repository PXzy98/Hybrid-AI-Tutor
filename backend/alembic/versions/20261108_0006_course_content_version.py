"""course content version

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-08 09:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0006'
down_revision: str | None = '0005'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # every content edit increments it; running processes reload the course content when it changes (Z9)
    op.add_column('course', sa.Column('content_version', sa.Integer(), server_default='0', nullable=False))


def downgrade() -> None:
    op.drop_column('course', 'content_version')
