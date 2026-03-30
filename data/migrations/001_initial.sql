-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "postgis";
CREATE EXTENSION IF NOT EXISTS "vector";
SELECT PostGIS_Version();

-- Blood group enum
CREATE TYPE blood_group_enum AS ENUM (
    'A+', 'A-', 'B+', 'B-', 'O+', 'O-', 'AB+', 'AB-'
);

-- Urgency enum
CREATE TYPE urgency_enum AS ENUM (
    'EMERGENCY', 'URGENT', 'PLANNED'
);

-- Request status enum
CREATE TYPE request_status_enum AS ENUM (
    'OPEN', 'MATCHED', 'FULFILLED', 'CANCELLED', 'EXPIRED'
);

-- Match status enum
CREATE TYPE match_status_enum AS ENUM (
    'PENDING', 'ACCEPTED', 'DECLINED', 'CONFIRMED', 'CANCELLED'
);

-- Notification range enum
CREATE TYPE notification_range_enum AS ENUM (
    'UNION', 'UPAZILA', 'DISTRICT', 'DIVISION'
);

-- Notification response enum
CREATE TYPE notif_response_enum AS ENUM (
    'SENT', 'OPENED', 'ACCEPTED', 'DECLINED', 'TIMEOUT'
);

-- ── TABLES ──────────────────────────────────────────────────────────────────

CREATE TABLE users (
    user_id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_hash      VARCHAR(64) NOT NULL UNIQUE,
    blood_group     blood_group_enum NOT NULL,
    is_active_donor BOOLEAN NOT NULL DEFAULT TRUE,
    next_eligible_date DATE,
    total_donations INTEGER NOT NULL DEFAULT 0,
    notification_range notification_range_enum NOT NULL DEFAULT 'UPAZILA',
    badge           VARCHAR(20) DEFAULT 'none',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE locations (
    location_id     UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id         UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    location_type   VARCHAR(20) NOT NULL DEFAULT 'current',
    division_id     INTEGER NOT NULL,
    district_id     INTEGER NOT NULL,
    upazila_id      INTEGER NOT NULL,
    union_id        INTEGER NOT NULL,
    division_name   VARCHAR(60),
    district_name   VARCHAR(60),
    upazila_name    VARCHAR(60),
    union_name      VARCHAR(60),
    coords          GEOGRAPHY(POINT, 4326),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE blood_requests (
    request_id      UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    requester_id    UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    blood_group     blood_group_enum NOT NULL,
    units_needed    SMALLINT NOT NULL DEFAULT 1,
    urgency         urgency_enum NOT NULL DEFAULT 'URGENT',
    hospital_name   TEXT,
    message         TEXT,
    needed_by       TIMESTAMPTZ,
    division_id     INTEGER NOT NULL,
    district_id     INTEGER NOT NULL,
    upazila_id      INTEGER NOT NULL,
    union_id        INTEGER NOT NULL,
    status          request_status_enum NOT NULL DEFAULT 'OPEN',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE matches (
    match_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id      UUID NOT NULL REFERENCES blood_requests(request_id) ON DELETE CASCADE,
    donor_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    status          match_status_enum NOT NULL DEFAULT 'PENDING',
    matched_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    confirmed_at    TIMESTAMPTZ,
    chat_channel_id UUID UNIQUE,
    UNIQUE(request_id, donor_id)
);

CREATE TABLE chat_messages (
    msg_id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    channel_id      UUID NOT NULL,
    sender_role     VARCHAR(10) NOT NULL CHECK (sender_role IN ('donor', 'requester')),
    content_raw     TEXT NOT NULL,
    content_scrubbed TEXT,
    pii_detected    BOOLEAN NOT NULL DEFAULT FALSE,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    is_read         BOOLEAN NOT NULL DEFAULT FALSE,
    deleted_at      TIMESTAMPTZ
);

CREATE TABLE notifications_log (
    notif_id        UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    request_id      UUID NOT NULL REFERENCES blood_requests(request_id) ON DELETE CASCADE,
    donor_id        UUID NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    tier_sent       notification_range_enum NOT NULL,
    response        notif_response_enum NOT NULL DEFAULT 'SENT',
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    responded_at    TIMESTAMPTZ
);

-- Donor embeddings for semantic search (pgvector)
CREATE TABLE donor_embeddings (
    user_id         UUID PRIMARY KEY REFERENCES users(user_id) ON DELETE CASCADE,
    embedding       vector(384),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);