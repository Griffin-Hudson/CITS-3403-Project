"""Initial schema: users, beats, likes, purchases, follows

Revision ID: e1a2b3c4d5e6
Revises:
Create Date: 2025-03-20 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'e1a2b3c4d5e6'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # follows — self-referential many-to-many for user follow relationships
    op.create_table(
        'follows',
        sa.Column('follower_id', sa.Integer(), nullable=False),
        sa.Column('followed_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['followed_id'], ['user.id']),
        sa.ForeignKeyConstraint(['follower_id'], ['user.id']),
        sa.PrimaryKeyConstraint('follower_id', 'followed_id'),
    )

    # user — covers both producers and listeners via the role field
    op.create_table(
        'user',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=False),
        sa.Column('role', sa.String(length=16), nullable=False),
        sa.Column('bio', sa.Text(), nullable=True),
        sa.Column('avatar_url', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
    )

    # beat — core content unit uploaded by producers
    op.create_table(
        'beat',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=128), nullable=False),
        sa.Column('audio_url', sa.String(length=256), nullable=False),
        sa.Column('cover_url', sa.String(length=256), nullable=True),
        sa.Column('genre', sa.String(length=64), nullable=True),
        sa.Column('bpm', sa.Integer(), nullable=True),
        sa.Column('key', sa.String(length=16), nullable=True),
        sa.Column('mood_tag', sa.String(length=64), nullable=True),
        sa.Column('licence_type', sa.String(length=64), nullable=True),
        sa.Column('price', sa.Float(), nullable=False),
        sa.Column('play_count', sa.Integer(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=True),
        sa.Column('producer_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['producer_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # like — tracks which user liked which beat (unique per user/beat pair)
    op.create_table(
        'like',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('beat_id', sa.Integer(), nullable=False),
        sa.Column('liked_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beat_id'], ['beat.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'beat_id', name='unique_like'),
    )

    # purchase — records completed beat transactions
    op.create_table(
        'purchase',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('buyer_id', sa.Integer(), nullable=False),
        sa.Column('beat_id', sa.Integer(), nullable=False),
        sa.Column('price_paid', sa.Float(), nullable=False),
        sa.Column('licence_type', sa.String(length=64), nullable=True),
        sa.Column('purchased_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beat_id'], ['beat.id']),
        sa.ForeignKeyConstraint(['buyer_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('purchase')
    op.drop_table('like')
    op.drop_table('beat')
    op.drop_table('user')
    op.drop_table('follows')
