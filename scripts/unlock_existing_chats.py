"""
Script to unlock all existing locked chats
Run this script to allow messaging in all chats
"""
import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def unlock_all_chats():
    """Update all locked chats to unlocked status"""
    async with async_engine.begin() as conn:
        print("Unlocking all locked chats...")

        # Update all locked chats to unlocked (using uppercase as stored in DB)
        result = await conn.execute(text("""
            UPDATE chats
            SET status = 'UNLOCKED'
            WHERE status = 'LOCKED'
            RETURNING id
        """))

        updated_ids = result.fetchall()
        count = len(updated_ids)

        if count == 0:
            print("No locked chats found.")
        else:
            print(f"Successfully unlocked {count} chat(s).")
            for row in updated_ids:
                print(f"  - Chat ID: {row[0]}")

        print("\nDone! All chats are now unlocked and ready for messaging.")


if __name__ == "__main__":
    asyncio.run(unlock_all_chats())
