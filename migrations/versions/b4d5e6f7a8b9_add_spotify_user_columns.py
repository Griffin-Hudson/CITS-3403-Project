"""Add spotify user columns

Revision ID: b4d5e6f7a8b9
Revises: a3c4d5e6f7a8
Create Date: 2026-05-15 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'b4d5e6f7a8b9'
down_revision = 'a3c4d5e6f7a8'
branch_labels = None
depends_on = None


def upgrade():
    from sqlalchemy import inspect, text
    conn = op.get_bind()
    existing = {c['name'] for c in inspect(conn).get_columns('user')}

    # DBs created from db.create_all() after the model was updated already have
    # these columns and the unique index — skip the whole migration in that case.
    if 'spotify_id' in existing:
        return

    with op.batch_alter_table('user') as batch_op:
        batch_op.add_column(sa.Column('spotify_id',           sa.String(length=128), nullable=True))
        batch_op.add_column(sa.Column('spotify_display_name', sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('spotify_url',          sa.String(length=256), nullable=True))
        batch_op.add_column(sa.Column('spotify_artist_url',   sa.String(length=256), nullable=True))

    # Create unique index directly — avoids a table rebuild and the FK constraint
    # error that batch_alter_table triggers when recreating the user table.
    conn.execute(text(
        'CREATE UNIQUE INDEX IF NOT EXISTS uq_user_spotify_id ON "user" (spotify_id)'
    ))


def downgrade():
    with op.batch_alter_table('user') as batch_op:
        batch_op.drop_constraint('uq_user_spotify_id', type_='unique')
        batch_op.drop_column('spotify_artist_url')
        batch_op.drop_column('spotify_url')
        batch_op.drop_column('spotify_display_name')
        batch_op.drop_column('spotify_id')
