"""add_is_sponsor_to_users

Revision ID: add_sponsor_001
Revises: add_stripe_001
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_sponsor_001'
down_revision = 'add_stripe_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add is_sponsor column to users table"""
    op.add_column('users', sa.Column('is_sponsor', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    """Remove is_sponsor column from users table"""
    op.drop_column('users', 'is_sponsor')
