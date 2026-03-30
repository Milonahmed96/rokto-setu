"""
agent/graph.py
--------------
LangGraph matching agent — the core AI brain of Rokto Setu.

Flow:
    START
      │
      ▼
    search_donors          ← query DB at current tier
      │
      ▼
    rank_donors            ← score by proximity + history
      │
      ▼
    decide_expand          ← should we expand radius?
      │
      ├─ yes → expand_tier → search_donors (loop)
      │
      └─ no  → notify_donors
                  │
                  ▼
               END
"""

import json
from datetime import datetime
from typing import Literal

from langgraph.graph import StateGraph, END

import anthropic

from agent.state import MatchingState
from agent.tools import query_donors, rank_donors, simulate_notification, log_decision
from agent.prompts import EXPANSION_SYSTEM
from api.database import settings

# Tier expansion order
TIER_ORDER = ["UNION", "UPAZILA", "DISTRICT", "DIVISION"]


# ── Node 1: Search donors at current tier ────────────────────────────────────

async def search_donors_node(state: MatchingState) -> MatchingState:
    tier = state["current_tier"]
    print(f"\n[AGENT] Searching at tier: {tier}")

    donors = await query_donors(
        blood_group = state["blood_group"],
        union_id    = state.get("union_id"),
        upazila_id  = state.get("upazila_id"),
        district_id = state.get("district_id"),
        division_id = state.get("division_id"),
        tier        = tier,
    )

    log_entry = {
        "step":          "search",
        "tier":          tier,
        "donors_found":  len(donors),
        "timestamp":     datetime.now().isoformat(),
    }

    print(f"[AGENT] Found {len(donors)} eligible donors at {tier} level")

    return {
        **state,
        "donors_found":  donors,
        "decision_log":  state.get("decision_log", []) + [log_entry],
    }


# ── Node 2: Rank donors ───────────────────────────────────────────────────────

async def rank_donors_node(state: MatchingState) -> MatchingState:
    donors = state["donors_found"]

    if not donors:
        return {**state, "donors_ranked": []}

    ranked = rank_donors(
        donors              = donors,
        request_union_id    = state.get("union_id", 0),
        request_upazila_id  = state.get("upazila_id", 0),
        request_district_id = state.get("district_id", 0),
    )

    log_entry = {
        "step":     "rank",
        "top_3":    [d["user_id"][:8] + "..." for d in ranked[:3]],
        "scores":   "proximity + donation history + badge + recency",
        "timestamp": datetime.now().isoformat(),
    }

    print(f"[AGENT] Ranked {len(ranked)} donors — top match: {ranked[0]['district_name'] if ranked else 'none'}")

    return {
        **state,
        "donors_ranked": ranked,
        "decision_log":  state.get("decision_log", []) + [log_entry],
    }


# ── Node 3: Decide whether to expand ─────────────────────────────────────────

async def decide_expand_node(state: MatchingState) -> MatchingState:
    donors   = state["donors_ranked"]
    tier     = state["current_tier"]
    urgency  = state["urgency"]

    # Hard rules first — no need for LLM
    if len(donors) == 0 and tier == "DIVISION":
        # Already at max tier — cannot expand further
        return {
            **state,
            "should_expand": False,
            "decision_log": state.get("decision_log", []) + [{
                "step":      "decide_expand",
                "decision":  "no — already at DIVISION tier",
                "timestamp": datetime.now().isoformat(),
            }],
        }

    if len(donors) >= 3:
        # Enough donors found — proceed to notify
        return {
            **state,
            "should_expand": False,
            "decision_log": state.get("decision_log", []) + [{
                "step":      "decide_expand",
                "decision":  f"no — {len(donors)} donors found, sufficient",
                "timestamp": datetime.now().isoformat(),
            }],
        }

    # Ask Claude to decide expansion for edge cases
    client = anthropic.AsyncAnthropic()
    prompt = f"""Current search state:
- Blood group: {state['blood_group']}
- Urgency: {urgency}
- Tier searched: {tier}
- Donors found: {len(donors)}
- Donors notified so far: {len(state.get('donors_notified', []))}

Should the agent expand the search radius to the next geographic tier?"""

    message = await client.messages.create(
        model      = "claude-sonnet-4-20250514",
        max_tokens = 200,
        system     = EXPANSION_SYSTEM,
        messages   = [{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        decision = json.loads(raw)
        should_expand = decision.get("should_expand", True)
        reason        = decision.get("reason", "")
    except Exception:
        should_expand = len(donors) < 2
        reason        = "fallback rule: expand if fewer than 2 donors"

    print(f"[AGENT] Expand decision: {should_expand} — {reason}")

    return {
        **state,
        "should_expand": should_expand,
        "decision_log":  state.get("decision_log", []) + [{
            "step":      "decide_expand",
            "decision":  f"{'yes' if should_expand else 'no'} — {reason}",
            "timestamp": datetime.now().isoformat(),
        }],
    }


# ── Node 4: Expand to next tier ───────────────────────────────────────────────

async def expand_tier_node(state: MatchingState) -> MatchingState:
    current = state["current_tier"]
    idx     = TIER_ORDER.index(current)

    if idx >= len(TIER_ORDER) - 1:
        return {**state, "should_expand": False}

    next_tier = TIER_ORDER[idx + 1]
    print(f"[AGENT] Expanding: {current} → {next_tier}")

    return {
        **state,
        "current_tier": next_tier,
        "decision_log": state.get("decision_log", []) + [{
            "step":      "expand",
            "from_tier": current,
            "to_tier":   next_tier,
            "timestamp": datetime.now().isoformat(),
        }],
    }


# ── Node 5: Notify top donors ─────────────────────────────────────────────────

async def notify_donors_node(state: MatchingState) -> MatchingState:
    ranked   = state["donors_ranked"]
    notified = list(state.get("donors_notified", []))

    if not ranked:
        print("[AGENT] No donors to notify")
        return {
            **state,
            "is_matched": False,
            "decision_log": state.get("decision_log", []) + [{
                "step":      "notify",
                "result":    "no donors available",
                "timestamp": datetime.now().isoformat(),
            }],
        }

    # Notify top 3 donors
    top_donors    = ranked[:3]
    accepted_id   = None

    print(f"[AGENT] Notifying top {len(top_donors)} donors...")

    for donor in top_donors:
        accepted = await simulate_notification(
            donor_id     = donor["user_id"],
            request_id   = state["request_id"],
            urgency      = state["urgency"],
            blood_group  = state["blood_group"],
            district_name = donor.get("district_name", ""),
        )

        notified.append(donor["user_id"])

        if accepted:
            accepted_id = donor["user_id"]
            print(f"[AGENT] ✓ Donor {donor['user_id'][:8]}... accepted!")
            break

    is_matched = accepted_id is not None

    log_entry = {
        "step":         "notify",
        "notified":     len(notified),
        "matched":      is_matched,
        "accepted_by":  accepted_id[:8] + "..." if accepted_id else None,
        "timestamp":    datetime.now().isoformat(),
    }

    return {
        **state,
        "donors_notified": notified,
        "donor_accepted":  accepted_id,
        "is_matched":      is_matched,
        "decision_log":    state.get("decision_log", []) + [log_entry],
    }


# ── Routing logic ─────────────────────────────────────────────────────────────

def should_expand_or_notify(state: MatchingState) -> Literal["expand_tier", "notify_donors"]:
    if state.get("should_expand") and state["current_tier"] != "DIVISION":
        return "expand_tier"
    return "notify_donors"


# ── Build the graph ───────────────────────────────────────────────────────────

def build_matching_agent():
    graph = StateGraph(MatchingState)

    graph.add_node("search_donors",  search_donors_node)
    graph.add_node("rank_donors",    rank_donors_node)
    graph.add_node("decide_expand",  decide_expand_node)
    graph.add_node("expand_tier",    expand_tier_node)
    graph.add_node("notify_donors",  notify_donors_node)

    graph.set_entry_point("search_donors")

    graph.add_edge("search_donors", "rank_donors")
    graph.add_edge("rank_donors",   "decide_expand")
    graph.add_conditional_edges(
        "decide_expand",
        should_expand_or_notify,
        {
            "expand_tier":   "expand_tier",
            "notify_donors": "notify_donors",
        },
    )
    graph.add_edge("expand_tier",   "search_donors")
    graph.add_edge("notify_donors", END)

    return graph.compile()


# Singleton — compiled once, reused across requests
matching_agent = build_matching_agent()


async def run_matching_agent(
    request_id:  str,
    blood_group: str,
    units_needed: int,
    urgency:     str,
    division_id: int,
    district_id: int,
    upazila_id:  int,
    union_id:    int,
) -> dict:
    """
    Entry point — called by the API when a blood request is submitted.
    Returns the final state including decision log.
    """
    initial_state: MatchingState = {
        "request_id":      request_id,
        "blood_group":     blood_group,
        "units_needed":    units_needed,
        "urgency":         urgency,
        "division_id":     division_id,
        "district_id":     district_id,
        "upazila_id":      upazila_id,
        "union_id":        union_id,
        "current_tier":    "UPAZILA",
        "donors_found":    [],
        "donors_ranked":   [],
        "donors_notified": [],
        "donor_accepted":  None,
        "decision_log":    [],
        "should_expand":   False,
        "is_matched":      False,
        "error":           None,
        "started_at":      datetime.now().isoformat(),
    }

    print(f"\n{'='*50}")
    print(f"[AGENT] Starting matching for request {request_id[:8]}...")
    print(f"[AGENT] Blood group: {blood_group} | Urgency: {urgency}")
    print(f"{'='*50}")

    final_state = await matching_agent.ainvoke(initial_state)

    print(f"\n[AGENT] Complete — matched: {final_state['is_matched']}")
    print(f"[AGENT] Decision log: {len(final_state['decision_log'])} steps")

    return final_state