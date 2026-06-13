"""Add pay, slots, job coordinates, and application distance columns

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-13 00:10:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('latitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('longitude', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pay_amount', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('pay_type', sa.String(length=20), nullable=True, server_default='fixed'))
        batch_op.add_column(sa.Column('slots_total', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('slots_filled', sa.Integer(), nullable=False, server_default='0'))

    with op.batch_alter_table('job_application', schema=None) as batch_op:
        batch_op.add_column(sa.Column('distance_km', sa.Float(), nullable=True))


def downgrade():
    with op.batch_alter_table('job_application', schema=None) as batch_op:
        batch_op.drop_column('distance_km')

    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_column('slots_filled')
        batch_op.drop_column('slots_total')
        batch_op.drop_column('pay_type')
        batch_op.drop_column('pay_amount')
        batch_op.drop_column('longitude')
        batch_op.drop_column('latitude')
