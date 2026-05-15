"""Add currency column to beat

Revision ID: c5e6f7a8b9c0
Revises: b4d5e6f7a8b9
Create Date: 2026-05-15 00:00:01.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'c5e6f7a8b9c0'
down_revision = 'b4d5e6f7a8b9'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('beat') as batch_op:
        batch_op.add_column(sa.Column(
            'currency', sa.String(length=3),
            nullable=False, server_default='USD',
        ))


def downgrade():
    with op.batch_alter_table('beat') as batch_op:
        batch_op.drop_column('currency')
