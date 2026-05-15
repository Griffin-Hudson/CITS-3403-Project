"""Add missing FK indexes to like, purchase, and comment tables

Revision ID: d6f7a8b9c0d1
Revises: c5e6f7a8b9c0
Create Date: 2026-05-15 12:00:00.000000

"""
from alembic import op


revision = 'd6f7a8b9c0d1'
down_revision = 'c5e6f7a8b9c0'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.create_index('ix_like_user_id', ['user_id'], unique=False)
        batch_op.create_index('ix_like_beat_id', ['beat_id'], unique=False)

    with op.batch_alter_table('purchase', schema=None) as batch_op:
        batch_op.create_index('ix_purchase_buyer_id', ['buyer_id'], unique=False)
        batch_op.create_index('ix_purchase_beat_id',  ['beat_id'],  unique=False)

    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.create_index('ix_comment_beat_id',   ['beat_id'],   unique=False)
        batch_op.create_index('ix_comment_author_id', ['author_id'], unique=False)
        batch_op.create_index('ix_comment_parent_id', ['parent_id'], unique=False)


def downgrade():
    with op.batch_alter_table('comment', schema=None) as batch_op:
        batch_op.drop_index('ix_comment_parent_id')
        batch_op.drop_index('ix_comment_author_id')
        batch_op.drop_index('ix_comment_beat_id')

    with op.batch_alter_table('purchase', schema=None) as batch_op:
        batch_op.drop_index('ix_purchase_beat_id')
        batch_op.drop_index('ix_purchase_buyer_id')

    with op.batch_alter_table('like', schema=None) as batch_op:
        batch_op.drop_index('ix_like_beat_id')
        batch_op.drop_index('ix_like_user_id')
