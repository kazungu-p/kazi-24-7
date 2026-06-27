"""Add job_ref column to job table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-27 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.add_column(sa.Column('job_ref', sa.String(length=12), nullable=True))
        batch_op.create_index('ix_job_job_ref', ['job_ref'], unique=True)


def downgrade():
    with op.batch_alter_table('job', schema=None) as batch_op:
        batch_op.drop_index('ix_job_job_ref')
        batch_op.drop_column('job_ref')
