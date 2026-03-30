from typing import TypedDict, Optional
from uuid import UUID
from datetime import datetime


class MatchingState(TypedDict):
    """
    State object passed between all nodes in the LangGraph matching agent.
    Every decision the agent makes is recorded here — full observability.
    """
    # Request details
    request_id:      str
    blood_group:     str
    units_needed:    int
    urgency:         str
    district_id:     int
    upazila_id:      int
    union_id:        int
    division_id:     int

    # Search state
    current_tier:    str          # UNION | UPAZILA | DISTRICT | DIVISION
    donors_found:    list[dict]   # raw query results
    donors_ranked:   list[dict]   # sorted by score
    donors_notified: list[str]    # user_ids notified so far
    donor_accepted:  Optional[str]  # user_id of accepting donor

    # Agent decisions log — shown in demo dashboard
    decision_log:    list[dict]

    # Control
    should_expand:   bool
    is_matched:      bool
    error:           Optional[str]
    started_at:      str