"""
Database setup script for Zerobin backend.
Creates initial database tables and optionally seeds test data.
"""
import asyncio
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import Base, async_engine
from app.core.security import get_password_hash
from app.models.user import User, UserType
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


async def create_tables():
    """Create all database tables"""
    print("Creating database tables...")
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created successfully!")


async def seed_test_users():
    """Create test users for each role"""
    print("\nSeeding test users...")

    AsyncSessionLocal = async_sessionmaker(
        async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with AsyncSessionLocal() as session:
        test_users = [
            {
                "email": "admin@zerobin.com",
                "password": "admin123",
                "full_name": "Admin User",
                "user_type": UserType.ADMIN,
                "is_superuser": True,
            },
            {
                "email": "citizen@zerobin.com",
                "password": "citizen123",
                "full_name": "Test Citizen",
                "user_type": UserType.CITIZEN,
            },
            {
                "email": "collector@zerobin.com",
                "password": "collector123",
                "full_name": "Test Collector",
                "user_type": UserType.COLLECTOR,
            },
            {
                "email": "kabadiwala@zerobin.com",
                "password": "kabadiwala123",
                "full_name": "Test Kabadiwala",
                "user_type": UserType.KABADIWALA,
            },
        ]

        for user_data in test_users:
            user = User(
                email=user_data["email"],
                hashed_password=get_password_hash(user_data["password"]),
                full_name=user_data["full_name"],
                user_type=user_data["user_type"],
                is_active=True,
                is_verified=True,
                is_superuser=user_data.get("is_superuser", False),
            )
            session.add(user)
            print(f"  Created: {user_data['email']} ({user_data['user_type'].value})")

        await session.commit()

    print("✅ Test users created successfully!")


async def main():
    """Main setup function"""
    print("=" * 60)
    print("Zerobin Database Setup")
    print("=" * 60)

    try:
        # Create tables
        await create_tables()

        # Ask if user wants to seed test data
        response = input("\nWould you like to create test users? (y/n): ")
        if response.lower() == 'y':
            await seed_test_users()
            print("\n" + "=" * 60)
            print("Test User Credentials:")
            print("=" * 60)
            print("Admin:      admin@zerobin.com / admin123")
            print("Citizen:    citizen@zerobin.com / citizen123")
            print("Collector:  collector@zerobin.com / collector123")
            print("Kabadiwala: kabadiwala@zerobin.com / kabadiwala123")
            print("=" * 60)

        print("\n✅ Setup complete! You can now start the server.")
        print("   Run: python main.py")

    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
