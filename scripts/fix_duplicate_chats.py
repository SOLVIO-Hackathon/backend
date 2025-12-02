"""
Script to remove duplicate chats and add unique constraint
Run this script to clean up existing duplicate chats in the database
"""
import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def fix_duplicate_chats():
    """Remove duplicate chats keeping only the most recent one"""
    async with async_engine.begin() as conn:
        print("Checking for duplicate chats...")

        # Find duplicate chats (same listing_id + buyer_id)
        result = await conn.execute(text("""
            SELECT listing_id, buyer_id, COUNT(*) as count
            FROM chats
            GROUP BY listing_id, buyer_id
            HAVING COUNT(*) > 1
        """))
        duplicates = result.fetchall()

        if not duplicates:
            print("No duplicate chats found.")
        else:
            print(f"Found {len(duplicates)} duplicate chat groups")

            # For each duplicate group, keep only the most recent chat
            for listing_id, buyer_id, count in duplicates:
                print(f"  Removing {count-1} duplicate(s) for listing {listing_id}, buyer {buyer_id}")

                # Delete all but the most recent chat
                await conn.execute(text("""
                    DELETE FROM chats
                    WHERE listing_id = :listing_id
                    AND buyer_id = :buyer_id
                    AND id NOT IN (
                        SELECT id FROM chats
                        WHERE listing_id = :listing_id AND buyer_id = :buyer_id
                        ORDER BY created_at DESC
                        LIMIT 1
                    )
                """), {"listing_id": listing_id, "buyer_id": buyer_id})

        print("\nAdding unique constraint...")

        # Check if constraint already exists
        constraint_check = await conn.execute(text("""
            SELECT constraint_name
            FROM information_schema.table_constraints
            WHERE table_name = 'chats'
            AND constraint_name = 'uq_chat_listing_buyer'
        """))

        if constraint_check.fetchone():
            print("Unique constraint already exists.")
        else:
            # Add unique constraint
            await conn.execute(text("""
                ALTER TABLE chats
                ADD CONSTRAINT uq_chat_listing_buyer
                UNIQUE (listing_id, buyer_id)
            """))
            print("Unique constraint added successfully.")

        print("\nDone! Database is now clean and protected against duplicate chats.")


if __name__ == "__main__":
    asyncio.run(fix_duplicate_chats())
