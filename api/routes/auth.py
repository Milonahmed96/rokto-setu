import hashlib
import random
import string
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from jose import jwt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db, settings
from api.models import RegisterRequest, OTPVerifyRequest, TokenResponse

router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory OTP store — fine for portfolio demo
# In production this would be Redis with TTL
_otp_store: dict[str, dict] = {}


def _hash_phone(phone: str) -> str:
    return hashlib.sha256(phone.encode()).hexdigest()


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


def _create_token(user_id: str) -> str:
    expire = datetime.utcnow() + timedelta(days=7)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


@router.post("/register", status_code=200)
async def register(
    body: RegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Step 1 of registration — validates phone, creates user if new,
    returns a simulated OTP (printed to logs in dev mode).
    """
    phone_hash = _hash_phone(body.phone)

    # Check if user already exists
    result = await db.execute(
        text("SELECT user_id FROM users WHERE phone_hash = :ph"),
        {"ph": phone_hash},
    )
    existing = result.fetchone()

    if not existing:
        # Create new user
        await db.execute(
            text("""
                INSERT INTO users
                    (phone_hash, blood_group, notification_range)
                VALUES
                    (:ph, :bg, :nr)
            """),
            {
                "ph": phone_hash,
                "bg": body.blood_group.value,
                "nr": body.notification_range.value,
            },
        )

    # Generate OTP — in dev we just print it, no real SMS
    otp = _generate_otp()
    _otp_store[body.phone] = {
        "otp": otp,
        "expires": datetime.utcnow() + timedelta(minutes=5),
        "blood_group": body.blood_group.value,
    }

    # In production: send via BD carrier SMS API
    # In dev: log it so you can use it
    print(f"[DEV] OTP for {body.phone}: {otp}")

    return {
        "message": "OTP sent",
        "phone": f"{body.phone[:5]}XXXXXX",
        "dev_note": f"Check container logs for OTP — no real SMS in dev mode",
    }


@router.post("/verify-otp", response_model=TokenResponse)
async def verify_otp(
    body: OTPVerifyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """
    Step 2 — validates OTP, returns JWT token.
    """
    stored = _otp_store.get(body.phone)

    if not stored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No OTP found for this number. Request a new one.",
        )

    if datetime.utcnow() > stored["expires"]:
        del _otp_store[body.phone]
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired. Request a new one.",
        )

    if body.otp != stored["otp"]:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid OTP.",
        )

    # OTP valid — fetch user
    phone_hash = _hash_phone(body.phone)
    result = await db.execute(
        text("SELECT user_id FROM users WHERE phone_hash = :ph"),
        {"ph": phone_hash},
    )
    user = result.fetchone()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    del _otp_store[body.phone]

    token = _create_token(str(user.user_id))

    return TokenResponse(
        access_token=token,
        user_id=user.user_id,
    )