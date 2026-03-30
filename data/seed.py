"""
data/seed.py
------------
Seeds the database with generated synthetic donor profiles.

Usage:
    python -m data.seed
    python -m data.seed --file data/synthetic/donors.json
"""

import argparse
import asyncio
import json
from pathlib import Path

import asyncpg
from api.database import settings


async def seed_donors(file_path: str):
    """Load donors from JSON and insert into database."""
    from datetime import date, datetime

    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}")
        print("Run 'python -m data.generate' first.")
        return

    with open(path, encoding="utf-8") as f:
        donors = json.load(f)

    print(f"\nSeeding {len(donors)} donors into database...")

    base_url = getattr(settings, "local_database_url", None) or settings.database_url
    db_url = base_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    inserted_users     = 0
    inserted_locations = 0
    skipped            = 0

    try:
        for donor in donors:
            try:
                # Convert date strings to Python date/datetime objects
                next_eligible = None
                if donor.get("next_eligible_date"):
                    next_eligible = date.fromisoformat(donor["next_eligible_date"])

                created_at = datetime.now()
                if donor.get("created_at"):
                    raw = donor["created_at"].replace("Z", "+00:00")
                    created_at = datetime.fromisoformat(raw)

                result = await conn.fetchrow(
                    """
                    INSERT INTO users
                        (phone_hash, blood_group, is_active_donor,
                         total_donations, next_eligible_date,
                         notification_range, badge, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    ON CONFLICT (phone_hash) DO NOTHING
                    RETURNING user_id
                    """,
                    donor["phone_hash"],
                    donor["blood_group"],
                    donor["is_active_donor"],
                    donor["total_donations"],
                    next_eligible,
                    donor["notification_range"],
                    donor["badge"],
                    created_at,
                )

                if not result:
                    skipped += 1
                    continue

                user_id = result["user_id"]
                inserted_users += 1

                await conn.execute(
                    """
                    INSERT INTO locations
                        (user_id, location_type,
                         division_id, district_id, upazila_id, union_id,
                         division_name, district_name, upazila_name, union_name)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                    ON CONFLICT (user_id) DO NOTHING
                    """,
                    user_id,
                    "current",
                    donor["division_id"],
                    donor["district_id"],
                    donor["upazila_id"],
                    donor["union_id"],
                    donor["division_name"],
                    donor["district_name"],
                    donor["upazila_name"],
                    donor["union_name"],
                )
                inserted_locations += 1

                if inserted_users % 50 == 0:
                    print(f"  {inserted_users} donors inserted...")

            except Exception as e:
                print(f"  Error inserting donor {donor['donor_index']}: {e}")
                skipped += 1

    finally:
        await conn.close()

    print(f"\n✓ Inserted {inserted_users} users")
    print(f"✓ Inserted {inserted_locations} locations")
    print(f"  Skipped {skipped} (duplicates or errors)")


async def verify_seed(expected: int):
    """Confirm row counts match expected."""
    # Use localhost when running outside Docker
    base_url = getattr(settings, "local_database_url", None) or settings.database_url
    db_url = base_url.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(db_url)

    try:
        user_count = await conn.fetchval("SELECT COUNT(*) FROM users")
        loc_count  = await conn.fetchval("SELECT COUNT(*) FROM locations")
        active     = await conn.fetchval(
            "SELECT COUNT(*) FROM users WHERE is_active_donor = TRUE"
        )

        blood_dist = await conn.fetch(
            """
            SELECT blood_group, COUNT(*) as cnt
            FROM users
            GROUP BY blood_group
            ORDER BY cnt DESC
            """
        )

        print(f"\n── Database verification ──────────────────")
        print(f"  Total users:     {user_count}")
        print(f"  Total locations: {loc_count}")
        print(f"  Active donors:   {active}")
        print(f"\n  Blood group distribution:")
        for row in blood_dist:
            bar = "█" * (row["cnt"] // 5)
            print(f"    {row['blood_group']:4s}  {row['cnt']:4d}  {bar}")

        if user_count >= expected * 0.95:
            print(f"\n✓ Seed verified — {user_count} donors in database")
        else:
            print(f"\n⚠ Only {user_count} donors found, expected ~{expected}")

    finally:
        await conn.close()


async def main():
    parser = argparse.ArgumentParser(description="Seed database with donor profiles")
    parser.add_argument(
        "--file", type=str,
        default="data/synthetic/donors.json",
        help="Path to generated donors JSON file",
    )
    parser.add_argument(
        "--verify-only", action="store_true",
        help="Only run verification, skip insert",
    )
    args = parser.parse_args()

    if not args.verify_only:
        await seed_donors(args.file)

    # Count expected from file
    path = Path(args.file)
    expected = 500
    if path.exists():
        with open(path, encoding="utf-8") as f:
            expected = len(json.load(f))

    await verify_seed(expected)


if __name__ == "__main__":
    asyncio.run(main())