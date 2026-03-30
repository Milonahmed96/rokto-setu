from datetime import datetime, date
from typing import Optional
from uuid import UUID
from enum import Enum
from pydantic import BaseModel, field_validator
import re


# ── Enums ─────────────────────────────────────────────────────────────────────

class BloodGroup(str, Enum):
    A_POS  = "A+"
    A_NEG  = "A-"
    B_POS  = "B+"
    B_NEG  = "B-"
    O_POS  = "O+"
    O_NEG  = "O-"
    AB_POS = "AB+"
    AB_NEG = "AB-"


class Urgency(str, Enum):
    EMERGENCY = "EMERGENCY"
    URGENT    = "URGENT"
    PLANNED   = "PLANNED"


class RequestStatus(str, Enum):
    OPEN      = "OPEN"
    MATCHED   = "MATCHED"
    FULFILLED = "FULFILLED"
    CANCELLED = "CANCELLED"
    EXPIRED   = "EXPIRED"


class MatchStatus(str, Enum):
    PENDING   = "PENDING"
    ACCEPTED  = "ACCEPTED"
    DECLINED  = "DECLINED"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class NotificationRange(str, Enum):
    UNION    = "UNION"
    UPAZILA  = "UPAZILA"
    DISTRICT = "DISTRICT"
    DIVISION = "DIVISION"


# ── Auth ──────────────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    phone: str
    blood_group: BloodGroup
    notification_range: NotificationRange = NotificationRange.UPAZILA

    @field_validator("phone")
    @classmethod
    def validate_bd_phone(cls, v):
        # Bangladesh phone: 01X-XXXXXXXX (11 digits starting with 01)
        pattern = r"^01[3-9]\d{8}$"
        cleaned = re.sub(r"[\s\-]", "", v)
        if not re.match(pattern, cleaned):
            raise ValueError("Invalid Bangladesh phone number. Format: 01XXXXXXXXX")
        return cleaned


class OTPVerifyRequest(BaseModel):
    phone: str
    otp: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID


# ── Location ──────────────────────────────────────────────────────────────────

class LocationUpdate(BaseModel):
    division_id:   int
    district_id:   int
    upazila_id:    int
    union_id:      int
    division_name: str
    district_name: str
    upazila_name:  str
    union_name:    str
    location_type: str = "current"


# ── User ──────────────────────────────────────────────────────────────────────

class UserProfile(BaseModel):
    user_id:            UUID
    blood_group:        BloodGroup
    is_active_donor:    bool
    next_eligible_date: Optional[date]
    total_donations:    int
    notification_range: NotificationRange
    badge:              str
    created_at:         datetime
    last_active:        datetime

    class Config:
        from_attributes = True


class DonorStatusUpdate(BaseModel):
    is_active: bool


# ── Blood Requests ────────────────────────────────────────────────────────────

class BloodRequestCreate(BaseModel):
    blood_group:   BloodGroup
    units_needed:  int = 1
    urgency:       Urgency = Urgency.URGENT
    hospital_name: Optional[str] = None
    message:       Optional[str] = None
    needed_by:     Optional[datetime] = None
    division_id:   int
    district_id:   int
    upazila_id:    int
    union_id:      int

    @field_validator("units_needed")
    @classmethod
    def validate_units(cls, v):
        if v < 1 or v > 10:
            raise ValueError("Units needed must be between 1 and 10")
        return v


class BloodRequestResponse(BaseModel):
    request_id:    UUID
    blood_group:   BloodGroup
    units_needed:  int
    urgency:       Urgency
    hospital_name: Optional[str]
    message:       Optional[str]
    needed_by:     Optional[datetime]
    district_id:   int
    upazila_id:    int
    status:        RequestStatus
    created_at:    datetime

    class Config:
        from_attributes = True


# ── Matches ───────────────────────────────────────────────────────────────────

class MatchResponse(BaseModel):
    match_id:        UUID
    request_id:      UUID
    status:          MatchStatus
    matched_at:      datetime
    chat_channel_id: Optional[UUID]

    model_config = {"from_attributes": True}


# ── Chat ──────────────────────────────────────────────────────────────────────

class ChatMessageSend(BaseModel):
    content: str

    @field_validator("content")
    @classmethod
    def validate_length(cls, v):
        if len(v.strip()) == 0:
            raise ValueError("Message cannot be empty")
        if len(v) > 1000:
            raise ValueError("Message too long — max 1000 characters")
        return v


class ChatMessageResponse(BaseModel):
    msg_id:          UUID
    sender_role:     str
    content_scrubbed: str
    pii_detected:    bool
    sent_at:         datetime
    is_read:         bool

    class Config:
        from_attributes = True


# ── Donor Search ──────────────────────────────────────────────────────────────

class DonorSearchParams(BaseModel):
    blood_group:  BloodGroup
    district_id:  Optional[int] = None
    upazila_id:   Optional[int] = None
    union_id:     Optional[int] = None


class DonorCountResponse(BaseModel):
    blood_group:  BloodGroup
    district_id:  int
    total_donors: int
    active_donors: int


# ── Agent ─────────────────────────────────────────────────────────────────────

class AgentDecisionLog(BaseModel):
    request_id:       UUID
    tier_searched:    NotificationRange
    donors_found:     int
    donors_notified:  int
    expansion_reason: Optional[str]
    timestamp:        datetime