"""Remove unused user role column

Revision ID: a3c4d5e6f7a8
Revises: f2b3c4d5e6a7
Create Date: 2026-05-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'a3c4d5e6f7a8'
down_revision = 'f2b3c4d5e6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_column('role')


def downgrade():
    # add with server_default so existing rows can backfill, then drop the
    # default so the column ends up matching the original schema
    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('role', sa.String(length=16), nullable=False, server_default='user'))
        batch_op.alter_column('role', server_default=None)
