"""
agent/tools.py
--------------
Tools available to the LangGraph matching agent.
Each tool is a pure async function — no side effects beyond DB reads/writes.
"""

import asyncio
from datetime import datetime, date
from typing import Optional
import asyncpg

from api.database import settings


async def _get_conn():
    # Inside Docker: use DATABASE_URL (hostname = db)
    # Outside Docker: use LOCAL_DATABASE_URL (hostname = localhost)
    db_url = settings.database_url.replace("postgresql+asyncpg://", "postgresql://")
    return await asyncpg.connect(db_url)


async def query_donors(
    blood_group: str,
    union_id:    Optional[int] = None,
    upazila_id:  Optional[int] = None,
    district_id: Optional[int] = None,
    division_id: Optional[int] = None,
    tier:        str = "UPAZILA",
) -> list[dict]:
    """
    Query active eligible donors matching blood group at a given location tier.
    Returns list of donor dicts with scoring metadata.
    """
    conn = await _get_conn()
    today = date.today()

    try:
        # Build WHERE clause based on tier
        if tier == "UNION" and union_id:
            location_filter = "l.union_id = $2"
            location_val    = union_id
        elif tier == "UPAZILA" and upazila_id:
            location_filter = "l.upazila_id = $2"
            location_val    = upazila_id
        elif tier == "DISTRICT" and district_id:
            location_filter = "l.district_id = $2"
            location_val    = district_id
        else:
            location_filter = "l.division_id = $2"
            location_val    = division_id

        rows = await conn.fetch(
            f"""
            SELECT
                u.user_id::text,
                u.blood_group,
                u.total_donations,
                u.next_eligible_date,
                u.badge,
                l.union_id,
                l.upazila_id,
                l.district_id,
                l.upazila_name,
                l.district_name,
                u.last_active
            FROM users u
            JOIN locations l ON u.user_id = l.user_id
            WHERE u.blood_group = $1
              AND u.is_active_donor = TRUE
              AND (u.next_eligible_date IS NULL OR u.next_eligible_date <= $3)
              AND {location_filter}
            ORDER BY u.last_active DESC
            LIMIT 20
            """,
            blood_group,
            location_val,
            today,
        )

        donors = []
        for r in rows:
            donors.append({
                "user_id":         r["user_id"],
                "blood_group":     r["blood_group"],
                "total_donations": r["total_donations"],
                "badge":           r["badge"],
                "upazila_name":    r["upazila_name"],
                "district_name":   r["district_name"],
                "union_id":        r["union_id"],
                "upazila_id":      r["upazila_id"],
                "district_id":     r["district_id"],
                "last_active":     r["last_active"].isoformat() if r["last_active"] else None,
            })
        return donors

    finally:
        await conn.close()


def rank_donors(
    donors:      list[dict],
    request_union_id:    int,
    request_upazila_id:  int,
    request_district_id: int,
) -> list[dict]:
    """
    Score and rank donors — no AI needed for pure proximity + history scoring.
    Higher score = better match.
    """
    def score(donor: dict) -> float:
        s = 0.0

        # Proximity scoring (0–50 points)
        if donor.get("union_id") == request_union_id:
            s += 50
        elif donor.get("upazila_id") == request_upazila_id:
            s += 35
        elif donor.get("district_id") == request_district_id:
            s += 20

        # Donation history (0–30 points)
        donations = donor.get("total_donations", 0)
        s += min(donations * 3, 30)

        # Badge bonus (0–10 points)
        badge_scores = {"legend": 10, "hero": 7, "lifesaver": 4, "none": 0}
        s += badge_scores.get(donor.get("badge", "none"), 0)

        # Recency (0–10 points) — penalise if last_active > 30 days ago
        if donor.get("last_active"):
            try:
                last = datetime.fromisoformat(donor["last_active"])
                days_ago = (datetime.now() - last.replace(tzinfo=None)).days
                if days_ago < 7:
                    s += 10
                elif days_ago < 30:
                    s += 5
            except Exception:
                pass

        return s

    return sorted(donors, key=score, reverse=True)


async def log_decision(
    request_id:   str,
    tier:         str,
    donors_found: int,
    notified:     int,
    reason:       str,
) -> dict:
    """Record an agent decision to the notifications log and return it."""
    entry = {
        "request_id":    request_id,
        "tier_searched": tier,
        "donors_found":  donors_found,
        "notified":      notified,
        "reason":        reason,
        "timestamp":     datetime.now().isoformat(),
    }

    conn = await _get_conn()
    try:
        # Log is append-only — immutable audit trail
        await conn.execute(
            """
            INSERT INTO notifications_log
                (request_id, donor_id, tier_sent, response, sent_at)
            SELECT $1::uuid, unnest($2::uuid[]), $3, 'SENT', NOW()
            """,
            request_id,
            [],  # donor_ids added separately per notification
            tier,
        )
    except Exception:
        pass  # Log failures should never break the match flow
    finally:
        await conn.close()

    return entry


async def simulate_notification(
    donor_id:   str,
    request_id: str,
    urgency:    str,
    blood_group: str,
    district_name: str,
) -> bool:
    """
    Simulate sending a push notification to a donor.
    In production: fires FCM via Firebase Admin SDK.
    In demo: logs the notification and returns True.
    """
    print(
        f"  [NOTIFICATION] → donor {donor_id[:8]}... "
        f"| {blood_group} needed | {district_name} | {urgency}"
    )

    # Simulate realistic response rate
    # In production this would be async — we'd wait for webhook callback
    import random
    response_delay = random.uniform(0.1, 0.5)
    await asyncio.sleep(response_delay)

    # 35% chance donor accepts in simulation
    accepted = random.random() < 0.35
    return accepted