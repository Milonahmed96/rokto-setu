from typing import Annotated
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import BloodRequestCreate, BloodRequestResponse, Urgency
from api.routes.auth import get_current_user

router = APIRouter(prefix="/requests", tags=["requests"])


@router.post("/create", status_code=201)
async def create_request(
    body: BloodRequestCreate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Submit a blood request — triggers the AI matching agent.
    For now stores the request and returns it.
    Agent wiring comes in Week 3.
    """
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
            "rid":      requester_id,
            "bg":       body.blood_group.value,
            "units":    body.units_needed,
            "urgency":  body.urgency.value,
            "hospital": body.hospital_name,
            "message":  body.message,
            "needed_by": body.needed_by,
            "div_id":   body.division_id,
            "dis_id":   body.district_id,
            "upa_id":   body.upazila_id,
            "uni_id":   body.union_id,
        },
    )
    row = result.fetchone()

    # TODO Week 3: trigger agent here
    # background_tasks.add_task(run_matching_agent, row.request_id)

    return {
        "request_id":   str(row.request_id),
        "blood_group":  row.blood_group,
        "units_needed": row.units_needed,
        "urgency":      row.urgency,
        "hospital_name": row.hospital_name,
        "message":      row.message,
        "district_id":  row.district_id,
        "upazila_id":   row.upazila_id,
        "status":       row.status,
        "created_at":   row.created_at.isoformat(),
        "agent_status": "queued — matching agent wired in Week 3",
    }


@router.get("/nearby")
async def get_nearby_requests(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Return open blood requests in the current user's district.
    Used by donors to see what is needed near them.
    """
    user_id = current_user["user_id"]

    # Get user's current location
    loc = await db.execute(
        text("""
            SELECT district_id, upazila_id
            FROM locations WHERE user_id = :uid
        """),
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
                "request_id":   str(r.request_id),
                "blood_group":  r.blood_group,
                "units_needed": r.units_needed,
                "urgency":      r.urgency,
                "hospital_name": r.hospital_name,
                "message":      r.message,
                "district_id":  r.district_id,
                "upazila_id":   r.upazila_id,
                "status":       r.status,
                "created_at":   r.created_at.isoformat(),
            }
            for r in rows
        ],
    }


@router.get("/my-history")
async def my_history(
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Return all requests made by the current user."""
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
                "request_id":   str(r.request_id),
                "blood_group":  r.blood_group,
                "units_needed": r.units_needed,
                "urgency":      r.urgency,
                "hospital_name": r.hospital_name,
                "status":       r.status,
                "created_at":   r.created_at.isoformat(),
            }
            for r in rows
        ],
    }