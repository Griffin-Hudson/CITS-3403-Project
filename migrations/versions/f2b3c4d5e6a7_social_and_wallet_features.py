"""Social features and wallet: comments, saves, transactions, play events

Adds the comment system (threading, likes, dislikes, reports), saved beats
library, wallet transaction ledger, play deduplication events, and extends
the user and beat tables with wallet balance and multi-tier pricing columns.

Revision ID: f2b3c4d5e6a7
Revises: e1a2b3c4d5e6
Create Date: 2025-04-10 14:30:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f2b3c4d5e6a7'
down_revision = 'e1a2b3c4d5e6'
branch_labels = None
depends_on = None


def upgrade():
    # ── Extend user with wallet balance and lifetime earnings ──────────────────
    op.add_column('user', sa.Column('balance', sa.Float(), nullable=False, server_default='0.0'))
    op.add_column('user', sa.Column('earnings', sa.Float(), nullable=False, server_default='0.0'))

    # ── Extend beat with trending flag, duration, and premium pricing tiers ───
    op.add_column('beat', sa.Column('duration', sa.String(length=10), nullable=True))
    op.add_column('beat', sa.Column('is_trending', sa.Boolean(), nullable=True))
    op.add_column('beat', sa.Column('premium_price', sa.Float(), nullable=True))
    op.add_column('beat', sa.Column('exclusive_price', sa.Float(), nullable=True))

    # ── Add indexes for frequently queried beat columns ────────────────────────
    op.create_index(op.f('ix_beat_genre'), 'beat', ['genre'], unique=False)
    op.create_index(op.f('ix_beat_play_count'), 'beat', ['play_count'], unique=False)
    op.create_index(op.f('ix_beat_producer_id'), 'beat', ['producer_id'], unique=False)
    op.create_index(op.f('ix_beat_uploaded_at'), 'beat', ['uploaded_at'], unique=False)

    # ── saved_beats — many-to-many user library ────────────────────────────────
    op.create_table(
        'saved_beats',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('beat_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['beat_id'], ['beat.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('user_id', 'beat_id'),
    )

    # ── comment — threaded via self-referential parent_id ─────────────────────
    op.create_table(
        'comment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('beat_id', sa.Integer(), nullable=False),
        sa.Column('author_id', sa.Integer(), nullable=False),
        sa.Column('parent_id', sa.Integer(), nullable=True),
        sa.Column('body', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('report_count', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['author_id'], ['user.id']),
        sa.ForeignKeyConstraint(['beat_id'], ['beat.id']),
        sa.ForeignKeyConstraint(['parent_id'], ['comment.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── comment_likes / comment_dislikes — mutually exclusive reactions ────────
    op.create_table(
        'comment_likes',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['comment.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('user_id', 'comment_id'),
    )

    op.create_table(
        'comment_dislikes',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['comment_id'], ['comment.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('user_id', 'comment_id'),
    )

    # ── comment_report — one row per user report; prevents duplicate reports ──
    op.create_table(
        'comment_report',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('comment_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('reason', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['comment_id'], ['comment.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('comment_id', 'user_id', name='unique_report'),
    )
    op.create_index(op.f('ix_comment_report_comment_id'), 'comment_report', ['comment_id'], unique=False)
    op.create_index(op.f('ix_comment_report_user_id'), 'comment_report', ['user_id'], unique=False)

    # ── transaction — wallet ledger for top-ups, purchases, and earnings ───────
    op.create_table(
        'transaction',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('type', sa.String(length=16), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('balance_after', sa.Float(), nullable=False),
        sa.Column('note', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_transaction_created_at'), 'transaction', ['created_at'], unique=False)
    op.create_index(op.f('ix_transaction_type'), 'transaction', ['type'], unique=False)
    op.create_index(op.f('ix_transaction_user_id'), 'transaction', ['user_id'], unique=False)

    # ── beat_play_event — deduplicates rapid play pings within an 8-second window
    op.create_table(
        'beat_play_event',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('beat_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('session_key', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['beat_id'], ['beat.id']),
        sa.ForeignKeyConstraint(['user_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_beat_play_event_beat_id'), 'beat_play_event', ['beat_id'], unique=False)
    op.create_index(op.f('ix_beat_play_event_created_at'), 'beat_play_event', ['created_at'], unique=False)
    op.create_index(op.f('ix_beat_play_event_session_key'), 'beat_play_event', ['session_key'], unique=False)
    op.create_index(op.f('ix_beat_play_event_user_id'), 'beat_play_event', ['user_id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_beat_play_event_user_id'), table_name='beat_play_event')
    op.drop_index(op.f('ix_beat_play_event_session_key'), table_name='beat_play_event')
    op.drop_index(op.f('ix_beat_play_event_created_at'), table_name='beat_play_event')
    op.drop_index(op.f('ix_beat_play_event_beat_id'), table_name='beat_play_event')
    op.drop_table('beat_play_event')

    op.drop_index(op.f('ix_transaction_user_id'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_type'), table_name='transaction')
    op.drop_index(op.f('ix_transaction_created_at'), table_name='transaction')
    op.drop_table('transaction')

    op.drop_index(op.f('ix_comment_report_user_id'), table_name='comment_report')
    op.drop_index(op.f('ix_comment_report_comment_id'), table_name='comment_report')
    op.drop_table('comment_report')
    op.drop_table('comment_dislikes')
    op.drop_table('comment_likes')
    op.drop_table('comment')
    op.drop_table('saved_beats')

    op.drop_index(op.f('ix_beat_uploaded_at'), table_name='beat')
    op.drop_index(op.f('ix_beat_producer_id'), table_name='beat')
    op.drop_index(op.f('ix_beat_play_count'), table_name='beat')
    op.drop_index(op.f('ix_beat_genre'), table_name='beat')
    op.drop_column('beat', 'exclusive_price')
    op.drop_column('beat', 'premium_price')
    op.drop_column('beat', 'is_trending')
    op.drop_column('beat', 'duration')

    op.drop_column('user', 'earnings')
    op.drop_column('user', 'balance')
