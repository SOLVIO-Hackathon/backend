"""add_ward_geohash_index

Revision ID: ward_geohash_001
Revises: add_sponsor_001
Create Date: 2025-12-01

"""
from alembic import op
import sqlalchemy as sa  # noqa: F401


# revision identifiers, used by Alembic.
revision = 'ward_geohash_001'
down_revision = 'add_sponsor_001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """
    Add ward_geohash column and indexes for better query performance.
    
    This migration:
    1. Adds a ward_geohash column (first 5 chars of geohash)
    2. Populates it from existing geohash data
    3. Creates an index on ward_geohash
    4. Creates a functional index on substr(geohash, 1, 5) as fallback
    """
    # Add ward_geohash column (nullable initially for existing rows)
    op.add_column('quests', sa.Column('ward_geohash', sa.String(5), nullable=True))
    
    # Populate ward_geohash from existing geohash values
    # Use raw SQL to ensure compatibility with PostgreSQL substring function
    op.execute("""
        UPDATE quests
        SET ward_geohash = SUBSTRING(geohash FROM 1 FOR 5)
        WHERE geohash IS NOT NULL
    """)
    
    # Now make it non-nullable with a default
    op.alter_column('quests', 'ward_geohash', nullable=False)
    
    # Create regular index on ward_geohash for fast lookups
    op.create_index('idx_quests_ward_geohash', 'quests', ['ward_geohash'])
    
    # Create composite index for common query patterns
    op.create_index(
        'idx_quests_ward_status',
        'quests',
        ['ward_geohash', 'status']
    )
    
    # Create functional index as fallback for direct geohash queries
    # This helps when filtering by geohash prefix patterns
    op.create_index(
        'idx_quests_geohash_prefix',
        'quests',
        [sa.text('SUBSTRING(geohash FROM 1 FOR 5)')],
        postgresql_using='btree'
    )


def downgrade() -> None:
    """Remove ward_geohash column and indexes"""
    op.drop_index('idx_quests_geohash_prefix', table_name='quests')
    op.drop_index('idx_quests_ward_status', table_name='quests')
    op.drop_index('idx_quests_ward_geohash', table_name='quests')
    op.drop_column('quests', 'ward_geohash')
