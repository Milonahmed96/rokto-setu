-- Users: blood group + donor status (most queried combo)
CREATE INDEX idx_users_blood_group
    ON users(blood_group);

CREATE INDEX idx_users_active_donor
    ON users(is_active_donor)
    WHERE is_active_donor = TRUE;

CREATE INDEX idx_users_eligible
    ON users(next_eligible_date)
    WHERE is_active_donor = TRUE;

-- Locations: all 4 tier IDs (geospatial matching core)
CREATE INDEX idx_locations_union
    ON locations(union_id);

CREATE INDEX idx_locations_upazila
    ON locations(upazila_id);

CREATE INDEX idx_locations_district
    ON locations(district_id);

CREATE INDEX idx_locations_division
    ON locations(division_id);

CREATE INDEX idx_locations_user
    ON locations(user_id);

-- Spatial index on geography column
CREATE INDEX idx_locations_coords
    ON locations USING GIST(coords);

-- Blood requests: open requests by location
CREATE INDEX idx_requests_status
    ON blood_requests(status)
    WHERE status = 'OPEN';

CREATE INDEX idx_requests_blood_group
    ON blood_requests(blood_group);

CREATE INDEX idx_requests_district
    ON blood_requests(district_id);

CREATE INDEX idx_requests_created
    ON blood_requests(created_at DESC);

-- Matches: lookup by request or donor
CREATE INDEX idx_matches_request
    ON matches(request_id);

CREATE INDEX idx_matches_donor
    ON matches(donor_id);

-- Chat: lookup by channel
CREATE INDEX idx_chat_channel
    ON chat_messages(channel_id, sent_at DESC)
    WHERE deleted_at IS NULL;

-- Notifications: lookup by request for agent tracking
CREATE INDEX idx_notif_request
    ON notifications_log(request_id, sent_at DESC);

-- Vector similarity search index
CREATE INDEX idx_donor_embeddings
    ON donor_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);