"""add_stripe_payment_method

Revision ID: add_stripe_001
Revises:
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_stripe_001'
down_revision = None  # Update this with your last migration ID if you have one
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add 'stripe' to the PaymentMethod enum"""
    # For PostgreSQL, we need to add the new enum value
    op.execute("ALTER TYPE paymentmethod ADD VALUE IF NOT EXISTS 'stripe'")


def downgrade() -> None:
    """Remove 'stripe' from PaymentMethod enum

    Note: PostgreSQL doesn't support removing enum values directly.
    This would require recreating the enum type and all dependent columns.
    For production, consider a more robust migration strategy.
    """
    # WARNING: This is a simplified downgrade that won't work in all cases
    # In production, you would need to:
    # 1. Create a new enum without 'stripe'
    # 2. Alter the column to use the new enum
    # 3. Drop the old enum
    pass
