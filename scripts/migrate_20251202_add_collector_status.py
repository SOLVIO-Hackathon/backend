import asyncio
from sqlalchemy import text
from app.core.database import async_engine

SQL = """
ALTER TABLE users
ADD COLUMN IF NOT EXISTS collector_status VARCHAR(20) DEFAULT 'available';
"""

async def run():
    async with async_engine.begin() as conn:
        await conn.execute(text(SQL))
        # Ensure default applied to existing NULLs
        await conn.execute(text("""
            UPDATE users SET collector_status = 'available' WHERE collector_status IS NULL;
        """))
    print("Migration applied: users.collector_status added/ensured.")

if __name__ == "__main__":
    asyncio.run(run())
