from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models import LocationUpdate
from api.routes.auth import get_current_user

router = APIRouter(prefix="/location", tags=["location"])


@router.put("/update")
async def update_location(
    body: LocationUpdate,
    current_user: Annotated[dict, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Update the current user's location."""
    user_id = current_user["user_id"]

    # Upsert — update if exists, insert if not
    await db.execute(
        text("""
            INSERT INTO locations
                (user_id, location_type,
                 division_id, district_id, upazila_id, union_id,
                 division_name, district_name, upazila_name, union_name,
                 updated_at)
            VALUES
                (:uid, :lt, :div_id, :dis_id, :upa_id, :uni_id,
                 :div_name, :dis_name, :upa_name, :uni_name, NOW())
            ON CONFLICT (user_id)
            DO UPDATE SET
                location_type  = EXCLUDED.location_type,
                division_id    = EXCLUDED.division_id,
                district_id    = EXCLUDED.district_id,
                upazila_id     = EXCLUDED.upazila_id,
                union_id       = EXCLUDED.union_id,
                division_name  = EXCLUDED.division_name,
                district_name  = EXCLUDED.district_name,
                upazila_name   = EXCLUDED.upazila_name,
                union_name     = EXCLUDED.union_name,
                updated_at     = NOW()
        """),
        {
            "uid":      user_id,
            "lt":       body.location_type,
            "div_id":   body.division_id,
            "dis_id":   body.district_id,
            "upa_id":   body.upazila_id,
            "uni_id":   body.union_id,
            "div_name": body.division_name,
            "dis_name": body.district_name,
            "upa_name": body.upazila_name,
            "uni_name": body.union_name,
        },
    )

    return {
        "message": "Location updated",
        "district": body.district_name,
        "upazila":  body.upazila_name,
        "union":    body.union_name,
    }


@router.get("/districts")
async def get_districts():
    """Return all 64 Bangladesh districts — hardcoded reference data."""
    return {"districts": BANGLADESH_DISTRICTS}


@router.get("/upazilas/{district_id}")
async def get_upazilas(district_id: int):
    """Return upazilas for a given district."""
    upazilas = BANGLADESH_UPAZILAS.get(district_id)
    if not upazilas:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"District {district_id} not found",
        )
    return {"district_id": district_id, "upazilas": upazilas}


# ── Reference data — Bangladesh administrative hierarchy ──────────────────────
# Subset for now — full 64 districts added in Week 2 data generation

BANGLADESH_DISTRICTS = [
    {"id": 1,  "name": "Dhaka",        "division_id": 1, "division_name": "Dhaka"},
    {"id": 2,  "name": "Gazipur",      "division_id": 1, "division_name": "Dhaka"},
    {"id": 3,  "name": "Narayanganj",  "division_id": 1, "division_name": "Dhaka"},
    {"id": 4,  "name": "Narsingdi",    "division_id": 1, "division_name": "Dhaka"},
    {"id": 5,  "name": "Manikganj",    "division_id": 1, "division_name": "Dhaka"},
    {"id": 6,  "name": "Munshiganj",   "division_id": 1, "division_name": "Dhaka"},
    {"id": 7,  "name": "Chittagong",   "division_id": 2, "division_name": "Chittagong"},
    {"id": 8,  "name": "Cox's Bazar",  "division_id": 2, "division_name": "Chittagong"},
    {"id": 9,  "name": "Sylhet",       "division_id": 3, "division_name": "Sylhet"},
    {"id": 10, "name": "Sunamganj",    "division_id": 3, "division_name": "Sylhet"},
    {"id": 11, "name": "Rajshahi",     "division_id": 4, "division_name": "Rajshahi"},
    {"id": 12, "name": "Khulna",       "division_id": 5, "division_name": "Khulna"},
    {"id": 13, "name": "Barisal",      "division_id": 6, "division_name": "Barisal"},
    {"id": 14, "name": "Rangpur",      "division_id": 7, "division_name": "Rangpur"},
    {"id": 15, "name": "Mymensingh",   "division_id": 8, "division_name": "Mymensingh"},
]

BANGLADESH_UPAZILAS = {
    1: [
        {"id": 101, "name": "Mirpur"},
        {"id": 102, "name": "Gulshan"},
        {"id": 103, "name": "Mohammadpur"},
        {"id": 104, "name": "Uttara"},
        {"id": 105, "name": "Demra"},
        {"id": 106, "name": "Savar"},
        {"id": 107, "name": "Dhanmondi"},
        {"id": 108, "name": "Motijheel"},
    ],
    7: [
        {"id": 701, "name": "Kotwali"},
        {"id": 702, "name": "Pahartali"},
        {"id": 703, "name": "Panchlaish"},
        {"id": 704, "name": "Halishahar"},
    ],
    9: [
        {"id": 901, "name": "Sylhet Sadar"},
        {"id": 902, "name": "Bianibazar"},
        {"id": 903, "name": "Golapganj"},
    ],
}