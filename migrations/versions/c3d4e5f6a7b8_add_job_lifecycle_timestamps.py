"""Add job lifecycle timestamps (started_at, completed_at)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-14 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('started_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('completed_at', sa.DateTime(), nullable=True))


def downgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_column('completed_at')
        batch_op.drop_column('started_at')
