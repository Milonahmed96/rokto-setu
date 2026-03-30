from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import BloodRequestCreate
from api.routes.auth import get_current_user

router = APIRouter(prefix="/requests", tags=["requests"])


import asyncio
from concurrent.futures import ThreadPoolExecutor

_executor = ThreadPoolExecutor(max_workers=4)


def _run_agent_task(
    request_id:  str,
    blood_group: str,
    units_needed: int,
    urgency:     str,
    division_id: int,
    district_id: int,
    upazila_id:  int,
    union_id:    int,
):
    """Run async agent in a separate thread with its own event loop."""
    async def _inner():
        from agent.graph import run_matching_agent
        result = await run_matching_agent(
            request_id   = request_id,
            blood_group  = blood_group,
            units_needed = units_needed,
            urgency      = urgency,
            division_id  = division_id,
            district_id  = district_id,
            upazila_id   = upazila_id,
            union_id     = union_id,
        )
        print(f"[AGENT] Task complete — matched: {result['is_matched']}", flush=True)
        for step in result["decision_log"]:
            print(f"[AGENT] {step}", flush=True)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_inner())
    except Exception as e:
        print(f"[AGENT] Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
    finally:
        loop.close()

@router.post("/create", status_code=201)
async def create_request(
    body:            BloodRequestCreate,
    background_tasks: BackgroundTasks,
    current_user:    Annotated[dict, Depends(get_current_user)],
    db:              Annotated[AsyncSession, Depends(get_db)],
):
    requester_id = current_user["user_id"]

    # Enforce max 3 active requests per user
    result = await db.execute(
        text("""
            SELECT COUNT(*) FROM blood_requests
            WHERE requester_id = :uid AND status = 'OPEN'
        """),
        {"uid": requester_id},
    )
    active_count = result.scalar()
    if active_count >= 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 3 active requests allowed at once.",
        )

    # Insert the request
    result = await db.execute(
        text("""
            INSERT INTO blood_requests
                (requester_id, blood_group, units_needed, urgency,
                 hospital_name, message, needed_by,
                 division_id, district_id, upazila_id, union_id)
            VALUES
                (:rid, :bg, :units, :urgency,
                 :hospital, :message, :needed_by,
                 :div_id, :dis_id, :upa_id, :uni_id)
            RETURNING
                request_id, blood_group, units_needed, urgency,
                hospital_name, message, needed_by,
                district_id, upazila_id, status, created_at
        """),
        {
            "rid":       requester_id,
            "bg":        body.blood_group.value,
            "units":     body.units_needed,
            "urgency":   body.urgency.value,
            "hospital":  body.hospital_name,
            "message":   body.message,
            "needed_by": body.needed_by,
            "div_id":    body.division_id,
            "dis_id":    body.district_id,
            "upa_id":    body.upazila_id,
            "uni_id":    body.union_id,
        },
    )
    row = result.fetchone()

    # Run agent in thread pool — avoids event loop conflicts
    import threading
    t = threading.Thread(
        target=_run_agent_task,
        kwargs=dict(
            request_id   = str(row.request_id),
            blood_group  = body.blood_group.value,
            units_needed = body.units_needed,
            urgency      = body.urgency.value,
            division_id  = body.division_id,
            district_id  = body.district_id,
            upazila_id   = body.upazila_id,
            union_id     = body.union_id,
        ),
        daemon=True,
    )
    t.start()

    return {
        "request_id":    str(row.request_id),
        "blood_group":   row.blood_group,
        "units_needed":  row.units_needed,
        "urgency":       row.urgency,
        "hospital_name": row.hospital_name,
        "message":       row.message,
        "district_id":   row.district_id,
        "upazila_id":    row.upazila_id,
        "status":        row.status,
        "created_at":    row.created_at.isoformat(),
        "agent_status":  "matching agent started",
    }


@router.get("/nearby")
async def get_nearby_requests(
    current_user: Annotated[dict, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
):
    user_id = current_user["user_id"]

    loc = await db.execute(
        text("SELECT district_id, upazila_id FROM locations WHERE user_id = :uid"),
        {"uid": user_id},
    )
    location = loc.fetchone()

    if not location:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Set your location first via PUT /location/update",
        )

    result = await db.execute(
        text("""
            SELECT
                request_id, blood_group, units_needed, urgency,
                hospital_name, message, needed_by,
                district_id, upazila_id, status, created_at
            FROM blood_requests
            WHERE district_id = :dis_id
              AND status = 'OPEN'
            ORDER BY
                CASE urgency
                    WHEN 'EMERGENCY' THEN 1
                    WHEN 'URGENT'    THEN 2
                    WHEN 'PLANNED'   THEN 3
                END,
                created_at DESC
            LIMIT 20
        """),
        {"dis_id": location.district_id},
    )
    rows = result.fetchall()

    return {
        "district_id": location.district_id,
        "total":       len(rows),
        "requests": [
            {
                "request_id":    str(r.request_id),
                "blood_group":   r.blood_group,
                "units_needed":  r.units_needed,
                "urgency":       r.urgency,
                "hospital_name": r.hospital_name,
                "message":       r.message,
                "district_id":   r.district_id,
                "upazila_id":    r.upazila_id,
                "status":        r.status,
                "created_at":    r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/my-history")
async def my_history(
    current_user: Annotated[dict, Depends(get_current_user)],
    db:           Annotated[AsyncSession, Depends(get_db)],
):
    result = await db.execute(
        text("""
            SELECT request_id, blood_group, units_needed, urgency,
                   hospital_name, status, created_at
            FROM blood_requests
            WHERE requester_id = :uid
            ORDER BY created_at DESC
            LIMIT 50
        """),
        {"uid": current_user["user_id"]},
    )
    rows = result.fetchall()

    return {
        "total": len(rows),
        "requests": [
            {
                "request_id":    str(r.request_id),
                "blood_group":   r.blood_group,
                "units_needed":  r.units_needed,
                "urgency":       r.urgency,
                "hospital_name": r.hospital_name,
                "status":        r.status,
                "created_at":    r.created_at.isoformat(),
            }
            for r in rows
        ],
    }