"""Check current chat statuses"""
import asyncio
from sqlalchemy import text
from app.core.database import async_engine


async def check_statuses():
    async with async_engine.begin() as conn:
        result = await conn.execute(text('SELECT id, status FROM chats'))
        chats = result.fetchall()
        if not chats:
            print("No chats found in database.")
        else:
            print(f"Found {len(chats)} chat(s):")
            for chat_id, status in chats:
                print(f"  - Chat {chat_id}: {status}")


if __name__ == "__main__":
    asyncio.run(check_statuses())
