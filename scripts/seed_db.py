"""Seed script to populate the database with sample data.

Usage:
    python scripts/seed_db.py            # Run interactive (asks before seeding all)
    python scripts/seed_db.py --yes       # Seed without confirmation

This script inserts sample rows for:
    - Users (admin, citizen, collector, kabadiwala)
    - Badges (for some users)
    - Listings (e-waste marketplace examples)
    - Bids (sample bids on listings)
    - Quests (reported waste cleanup tasks)

Idempotency:
    - Users are checked by email before creation
    - Listings / Quests / Bids sample entries only created if their count is zero

PostGIS:
    - Geometry POINT values are inserted using WKTElement with SRID 4326

Environment:
    Ensure database settings are correctly loaded via `.env` before running.
"""

import asyncio
import sys
from decimal import Decimal
from pathlib import Path

from typing import List

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from geoalchemy2 import WKTElement

from app.core.database import async_engine, init_db
from app.core.security import get_password_hash

from app.models.user import User, UserType
from app.models.badge import Badge, BadgeType
from app.models.listing import Listing, DeviceType, DeviceCondition, ListingStatus
from app.models.bid import Bid, BidStatus
from app.models.quest import Quest, WasteType, Severity, QuestStatus


AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_or_create_user(session: AsyncSession, *, email: str, password: str, full_name: str, user_type: UserType, **flags) -> User:
    result = await session.execute(select(User).where(User.email == email))
    user = result.scalars().first()
    if user:
        return user
    user = User(
        email=email,
        hashed_password=get_password_hash(password),
        full_name=full_name,
        user_type=user_type,
        is_active=True,
        is_verified=True,
        is_superuser=flags.get("is_superuser", False),
        is_sponsor=flags.get("is_sponsor", False),
    )
    session.add(user)
    await session.flush()  # assign PK
    print(f"  User created: {email} ({user_type.value})")
    return user


async def seed_users(session: AsyncSession) -> List[User]:
    print("Seeding users...")
    users = [
        await get_or_create_user(session, email="admin@example.com", password="admin123", full_name="Admin User", user_type=UserType.ADMIN, is_superuser=True),
        await get_or_create_user(session, email="citizen@example.com", password="citizen123", full_name="Citizen Alpha", user_type=UserType.CITIZEN),
        await get_or_create_user(session, email="collector@example.com", password="collector123", full_name="Collector Beta", user_type=UserType.COLLECTOR),
        await get_or_create_user(session, email="kabadiwala@example.com", password="kabadiwala123", full_name="Kabadiwala Gamma", user_type=UserType.KABADIWALA),
    ]
    await session.commit()
    return users


async def seed_badges(session: AsyncSession, users: List[User]):
    print("Seeding badges (if none exist)...")
    count = (await session.execute(select(Badge))).scalars().first()
    if count:
        print("  Badges already present; skipping.")
        return
    badge_rows = [
        Badge(user_id=users[1].id, badge_type=BadgeType.RECYCLING_CHAMPION),
        Badge(user_id=users[2].id, badge_type=BadgeType.TOP_COLLECTOR),
        Badge(user_id=users[3].id, badge_type=BadgeType.TRUSTED_KABADIWALA),
    ]
    session.add_all(badge_rows)
    await session.commit()
    print(f"  Inserted {len(badge_rows)} badges.")


async def seed_listings(session: AsyncSession, users: List[User]):
    print("Seeding listings (if none exist)...")
    existing = (await session.execute(select(Listing))).scalars().first()
    if existing:
        print("  Listings already present; skipping.")
        return
    seller = users[3]  # kabadiwala as seller for demo
    sample_listings = [
        Listing(
            seller_id=seller.id,
            device_type=DeviceType.MOBILE,
            device_name="Old Smartphone",
            condition=DeviceCondition.PARTIALLY_WORKING,
            image_urls=["https://example.com/img/phone1.jpg"],
            description="Cracked screen, battery okay.",
            estimated_value_min=Decimal("500.00"),
            estimated_value_max=Decimal("800.00"),
            location=WKTElement("POINT(90.4125 23.8103)", srid=4326),
            status=ListingStatus.LISTED,
        ),
        Listing(
            seller_id=seller.id,
            device_type=DeviceType.LAPTOP,
            device_name="Legacy Laptop",
            condition=DeviceCondition.NOT_WORKING,
            image_urls=["https://example.com/img/laptop1.jpg"],
            description="Does not boot; for parts only.",
            estimated_value_min=Decimal("1000.00"),
            estimated_value_max=Decimal("1500.00"),
            location=WKTElement("POINT(90.4000 23.8200)", srid=4326),
            status=ListingStatus.LISTED,
        ),
    ]
    session.add_all(sample_listings)
    await session.flush()
    print(f"  Inserted {len(sample_listings)} listings.")
    await session.commit()
    return sample_listings


async def seed_bids(session: AsyncSession, listings: List[Listing], users: List[User]):
    print("Seeding bids (if none exist)...")
    existing = (await session.execute(select(Bid))).scalars().first()
    if existing:
        print("  Bids already present; skipping.")
        return
    kabadiwala = users[3]
    bids = [
        Bid(
            listing_id=listings[0].id,
            kabadiwala_id=kabadiwala.id,
            offered_price=Decimal("600.00"),
            pickup_time_estimate="24h",
            message="Can pick up tomorrow morning.",
            status=BidStatus.PENDING,
        ),
        Bid(
            listing_id=listings[1].id,
            kabadiwala_id=kabadiwala.id,
            offered_price=Decimal("1100.00"),
            pickup_time_estimate="48h",
            message="Need to arrange transport.",
            status=BidStatus.PENDING,
        ),
    ]
    session.add_all(bids)
    await session.commit()
    print(f"  Inserted {len(bids)} bids.")


async def seed_quests(session: AsyncSession, users: List[User]):
    print("Seeding quests (if none exist)...")
    existing = (await session.execute(select(Quest))).scalars().first()
    if existing:
        print("  Quests already present; skipping.")
        return
    reporter = users[1]  # citizen
    sample_quests = [
        Quest(
            reporter_id=reporter.id,
            title="Overflowing Recycling Bin",
            description="Bin near park entrance is overflowing.",
            location=WKTElement("POINT(90.4150 23.8050)", srid=4326),
            geohash="wsq0x1abc123",  # placeholder geohash
            ward_geohash="wsq0x",
            waste_type=WasteType.RECYCLABLE,
            severity=Severity.MEDIUM,
            status=QuestStatus.REPORTED,
            bounty_points=50,
            image_url="https://example.com/img/recycle_bin.jpg",
        ),
        Quest(
            reporter_id=reporter.id,
            title="E-waste Dump Spot",
            description="Several old electronics discarded behind market.",
            location=WKTElement("POINT(90.4180 23.8090)", srid=4326),
            geohash="wsq0x1def456",
            ward_geohash="wsq0x",
            waste_type=WasteType.E_WASTE,
            severity=Severity.HIGH,
            status=QuestStatus.REPORTED,
            bounty_points=120,
            image_url="https://example.com/img/ewaste_dump.jpg",
        ),
    ]
    session.add_all(sample_quests)
    await session.commit()
    print(f"  Inserted {len(sample_quests)} quests.")


async def seed_all(confirm: bool = True):
    if confirm:
        resp = input("Proceed with seeding sample data? (y/n): ").strip().lower()
        if resp not in {"y", "yes"}:
            print("Aborted by user.")
            return

    # Ensure tables & extensions exist
    print("Initializing database (tables/extensions)...")
    await init_db()

    async with AsyncSessionLocal() as session:
        users = await seed_users(session)
        await seed_badges(session, users)
        listings = await seed_listings(session, users) or []
        if listings:
            await seed_bids(session, listings, users)
        await seed_quests(session, users)

    print("\n✅ Seeding complete.")


def parse_args():
    import argparse
    parser = argparse.ArgumentParser(description="Seed database with sample data")
    parser.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    return parser.parse_args()


async def main():
    args = parse_args()
    await seed_all(confirm=not args.yes)


if __name__ == "__main__":
    asyncio.run(main())
