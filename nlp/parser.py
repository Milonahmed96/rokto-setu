"""
nlp/parser.py
-------------
Natural language blood request parser.

Converts free-text like:
  "আমার মায়ের জন্য আজকে O নেগেটিভ রক্ত দরকার ঢাকা মেডিকেলে"
  "need 2 bags O- urgent DMCH tomorrow morning"

Into structured fields:
  blood_group, units_needed, urgency, hospital_name, needed_by
"""

import json
import re
from datetime import datetime, timedelta
from typing import Optional

import anthropic


# ── Quick regex pre-pass ──────────────────────────────────────────────────────

BLOOD_GROUP_PATTERNS = {
    "O-":  [r"O\s*[-–]\s*(?:\b|$)", r"O\s*negative", r"O\s*neg\b"],
    "O+":  [r"O\s*[+]\s*(?:\b|$)", r"O\s*positive", r"O\s*pos\b"],
    "A-":  [r"(?<![AB])\bA\s*[-–]", r"(?<![AB])\bA\s*negative", r"(?<![AB])\bA\s*neg\b"],
    "A+":  [r"(?<![AB])\bA\s*[+]", r"(?<![AB])\bA\s*positive", r"(?<![AB])\bA\s*pos\b"],
    "B-":  [r"(?<!A)\bB\s*[-–]", r"(?<!A)\bB\s*negative", r"(?<!A)\bB\s*neg\b"],
    "B+":  [r"(?<!A)\bB\s*[+]", r"(?<!A)\bB\s*positive", r"(?<!A)\bB\s*pos\b"],
    "AB-": [r"\bAB\s*[-–]", r"\bAB\s*negative", r"\bAB\s*neg\b"],
    "AB+": [r"\bAB\s*[+]", r"\bAB\s*positive", r"\bAB\s*pos\b"],
}

URGENCY_PATTERNS = {
    "EMERGENCY": [r"\bemergency\b", r"\bimmediately\b", r"এখনই", r"জরুরি"],
    "URGENT":    [r"\burgent\b", r"\btoday\b", r"আজ\b", r"\bquick\b"],
    "PLANNED":   [r"\btomorrow\b", r"\bplanned\b", r"\bscheduled\b", r"কাল"],
}

UNIT_PATTERN = re.compile(r"\b(\d+)\s*(?:unit|bag|ব্যাগ|পিন্ট|pint)s?\b", re.IGNORECASE)


def _quick_parse(text: str) -> dict:
    """Regex pre-pass — catches obvious structured patterns instantly."""
    result = {}

    # Blood group
    text_upper = text.upper()
    for group, patterns in BLOOD_GROUP_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result["blood_group"] = group
                break
        if "blood_group" in result:
            break

    # Units
    unit_match = UNIT_PATTERN.search(text)
    if unit_match:
        result["units_needed"] = min(int(unit_match.group(1)), 10)

    # Urgency
    for urgency, patterns in URGENCY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                result["urgency"] = urgency
                break
        if "urgency" in result:
            break

    return result


async def parse_blood_request(text: str) -> dict:
    """
    Full NLP parser — regex pre-pass then Claude for structured extraction.

    Returns dict with fields:
        blood_group, units_needed, urgency, hospital_name, notes
    """
    # Quick pass first
    quick = _quick_parse(text)

    # If we already have all critical fields, skip Claude
    if "blood_group" in quick and "urgency" in quick:
        return {
            "blood_group":   quick.get("blood_group"),
            "units_needed":  quick.get("units_needed", 1),
            "urgency":       quick.get("urgency", "URGENT"),
            "hospital_name": None,
            "notes":         text,
            "parsed_by":     "regex",
        }

    # Claude pass for complex/Bengali requests
    client = anthropic.AsyncAnthropic()

    prompt = f"""Extract blood request details from this message. The message may be in English, Bengali, or mixed Banglish.

Message: "{text}"

Return ONLY a JSON object with these fields:
{{
  "blood_group": "one of: A+, A-, B+, B-, O+, O-, AB+, AB- or null if unclear",
  "units_needed": "integer 1-10, default 1",
  "urgency": "one of: EMERGENCY, URGENT, PLANNED — infer from context",
  "hospital_name": "hospital name if mentioned, else null",
  "notes": "any other relevant details"
}}"""

    message = await client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 300,
        messages   = [{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    raw = raw.strip()

    try:
        parsed = json.loads(raw)
        parsed["parsed_by"] = "claude"
        return parsed
    except Exception:
        return {
            "blood_group":   quick.get("blood_group"),
            "units_needed":  quick.get("units_needed", 1),
            "urgency":       quick.get("urgency", "URGENT"),
            "hospital_name": None,
            "notes":         text,
            "parsed_by":     "fallback",
        }