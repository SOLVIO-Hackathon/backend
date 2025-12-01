"""add_new_features_tables

Revision ID: add_features_001
Revises: add_stripe_001
Create Date: 2025-12-01

Adds tables for:
- chats (in-app messaging)
- chat_messages
- admin_reviews (human-in-the-loop)
- disposal_points (waste routing)
- payouts (payment disbursement)
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID
from geoalchemy2 import Geometry


# revision identifiers, used by Alembic.
revision = 'add_features_001'
down_revision = 'add_stripe_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create new feature tables and enums"""

    # Create new enums
    op.execute("CREATE TYPE chatstatus AS ENUM ('locked', 'unlocked', 'closed')")
    op.execute("CREATE TYPE reviewstatus AS ENUM ('pending', 'approved', 'rejected')")
    op.execute("CREATE TYPE flagreason AS ENUM ('low_ai_confidence', 'suspicious_activity', 'user_report', 'fraud_detection', 'location_mismatch')")
    op.execute("CREATE TYPE disposalpointtype AS ENUM ('recycling_center', 'landfill', 'e_waste_center', 'organic_composting', 'hazardous_waste')")
    op.execute("CREATE TYPE payoutstatus AS ENUM ('pending', 'processing', 'completed', 'failed')")
    op.execute("CREATE TYPE payoutmethod AS ENUM ('stripe_transfer', 'bank_transfer', 'wallet')")

    # Create chats table
    op.create_table(
        'chats',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('listing_id', UUID(as_uuid=True), sa.ForeignKey('listings.id'), nullable=False, index=True),
        sa.Column('seller_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('buyer_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('status', sa.Enum('locked', 'unlocked', 'closed', name='chatstatus'), default='locked', index=True),
        sa.Column('deal_confirmed', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create chat_messages table
    op.create_table(
        'chat_messages',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('chat_id', UUID(as_uuid=True), sa.ForeignKey('chats.id'), nullable=False, index=True),
        sa.Column('sender_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.Text, nullable=False),
        sa.Column('is_read', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
    )

    # Create admin_reviews table
    op.create_table(
        'admin_reviews',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('quest_id', UUID(as_uuid=True), sa.ForeignKey('quests.id'), nullable=False, index=True),
        sa.Column('reviewer_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('flag_reason', sa.Enum('low_ai_confidence', 'suspicious_activity', 'user_report', 'fraud_detection', 'location_mismatch', name='flagreason'), nullable=False),
        sa.Column('ai_confidence_score', sa.Float, nullable=True),
        sa.Column('status', sa.Enum('pending', 'approved', 'rejected', name='reviewstatus'), default='pending', index=True),
        sa.Column('ai_notes', sa.Text, nullable=True),
        sa.Column('admin_notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('reviewed_at', sa.DateTime, nullable=True),
    )

    # Create disposal_points table
    op.create_table(
        'disposal_points',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('point_type', sa.Enum('recycling_center', 'landfill', 'e_waste_center', 'organic_composting', 'hazardous_waste', name='disposalpointtype'), nullable=False, index=True),
        sa.Column('location', Geometry('POINT', srid=4326), nullable=False),
        sa.Column('operating_hours', sa.String(255), nullable=True),
        sa.Column('contact_phone', sa.String(20), nullable=True),
        sa.Column('accepted_waste_types', sa.String(255), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Create payouts table
    op.create_table(
        'payouts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=False, index=True),
        sa.Column('transaction_id', UUID(as_uuid=True), sa.ForeignKey('transactions.id'), nullable=True),
        sa.Column('amount', sa.DECIMAL(10, 2), nullable=False),
        sa.Column('currency', sa.String(3), default='USD'),
        sa.Column('payout_method', sa.Enum('stripe_transfer', 'bank_transfer', 'wallet', name='payoutmethod'), nullable=False),
        sa.Column('status', sa.Enum('pending', 'processing', 'completed', 'failed', name='payoutstatus'), default='pending', index=True),
        sa.Column('stripe_transfer_id', sa.String(100), nullable=True),
        sa.Column('stripe_account_id', sa.String(100), nullable=True),
        sa.Column('bank_account_last4', sa.String(4), nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('failure_reason', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, default=sa.func.now()),
        sa.Column('processed_at', sa.DateTime, nullable=True),
    )

    # Create spatial index on disposal_points location
    op.execute('CREATE INDEX idx_disposal_points_location ON disposal_points USING GIST (location)')


def downgrade() -> None:
    """Drop feature tables and enums"""
    op.drop_table('payouts')
    op.drop_table('disposal_points')
    op.drop_table('admin_reviews')
    op.drop_table('chat_messages')
    op.drop_table('chats')

    op.execute('DROP TYPE IF EXISTS payoutmethod')
    op.execute('DROP TYPE IF EXISTS payoutstatus')
    op.execute('DROP TYPE IF EXISTS disposalpointtype')
    op.execute('DROP TYPE IF EXISTS flagreason')
    op.execute('DROP TYPE IF EXISTS reviewstatus')
    op.execute('DROP TYPE IF EXISTS chatstatus')
