"""course_id on request logs and conversation turns

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11 12:00:00
"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '0011'
down_revision: str | None = '0010'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TABLES = ('request_log', 'session_turn')

# Rows written before this revision belong to the course API v1 served: the demo course, else the oldest
BACKFILL = (
    "UPDATE {table} SET course_id = (SELECT id FROM course ORDER BY (code = 'MED 0000') DESC, id LIMIT 1) "
    "WHERE course_id IS NULL"
)


def upgrade() -> None:
    for table in TABLES:
        op.add_column(table, sa.Column('course_id', sa.Integer(), nullable=True))
        op.create_foreign_key(f'{table}_course_id_fkey', table, 'course', ['course_id'], ['id'],
                              ondelete='CASCADE')
        op.create_index(op.f(f'ix_{table}_course_id'), table, ['course_id'], unique=False)
        op.execute(BACKFILL.format(table=table))


def downgrade() -> None:
    for table in TABLES:
        op.drop_index(op.f(f'ix_{table}_course_id'), table_name=table)
        op.drop_constraint(f'{table}_course_id_fkey', table, type_='foreignkey')
        op.drop_column(table, 'course_id')
