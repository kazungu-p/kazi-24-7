"""Add payment table for M-Pesa escrow and payouts

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-28 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = 'f6a7b8c9d0e1'
down_revision = 'e5f6a7b8c9d0'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('payment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('job_id', sa.Integer(), nullable=False),
        sa.Column('payer_id', sa.Integer(), nullable=True),
        sa.Column('payee_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('phone_number', sa.String(length=20), nullable=True),
        sa.Column('mpesa_checkout_id', sa.String(length=100), nullable=True),
        sa.Column('mpesa_receipt', sa.String(length=50), nullable=True),
        sa.Column('b2c_conversation_id', sa.String(length=100), nullable=True),
        sa.Column('b2c_originator_id', sa.String(length=100), nullable=True),
        sa.Column('type', sa.String(length=20), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['job_id'], ['job.id']),
        sa.ForeignKeyConstraint(['payer_id'], ['user.id']),
        sa.ForeignKeyConstraint(['payee_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('mpesa_checkout_id')
    )


def downgrade():
    op.drop_table('payment')
