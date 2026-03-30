"""
nlp/scrubber.py
---------------
PII detection and scrubbing for anonymous chat messages.

Detects and strips:
- Bangladesh phone numbers (01X-XXXXXXXX)
- Email addresses
- Names (via pattern heuristics + Claude fallback)
- Explicit identity reveals ("I am X", "my name is X")

Pipeline:
    raw message
        → regex pass (phones, emails, URLs)
        → pattern pass (name reveals)
        → Claude pass (Bengali/Banglish edge cases)
        → scrubbed message
"""

import re
import anthropic
from dataclasses import dataclass


@dataclass
class ScrubResult:
    original:     str
    scrubbed:     str
    pii_detected: bool
    items_found:  list[str]   # what types of PII were found


# ── Regex patterns ────────────────────────────────────────────────────────────

# Bangladesh mobile: 01X-XXXXXXXX (with optional spaces/dashes)
BD_PHONE = re.compile(
    r"01[3-9][\-]?\d{1,2}[\s\-]?\d{3,4}[\s\-]?\d{4}"
)
# Email addresses
EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Z|a-z]{2,}\b"
)

# URLs
URL = re.compile(
    r"https?://\S+|www\.\S+"
)

# Explicit name reveals (English)
NAME_REVEAL_EN = re.compile(
    r"\b(?:my name is|i am|i'm|call me|this is)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
    re.IGNORECASE,
)

# Explicit name reveals (Bengali transliteration patterns)
NAME_REVEAL_BN = re.compile(
    r"(?:আমি|আমার নাম|আমাকে)\s+[\u0980-\u09FF]+",
)

# WhatsApp/Telegram/social handles
SOCIAL_HANDLE = re.compile(
    r"@[A-Za-z0-9_]{3,}"
)


def _regex_scrub(text: str) -> tuple[str, list[str]]:
    """Fast first pass — catches 95% of PII with zero API cost."""
    found = []
    result = text

    # Phone numbers
    phones = BD_PHONE.findall(result)
    if phones:
        found.append(f"phone ({len(phones)} found)")
        result = BD_PHONE.sub("[phone removed]", result)

    # Emails
    emails = EMAIL.findall(result)
    if emails:
        found.append(f"email ({len(emails)} found)")
        result = EMAIL.sub("[email removed]", result)

    # URLs
    urls = URL.findall(result)
    if urls:
        found.append(f"url ({len(urls)} found)")
        result = URL.sub("[link removed]", result)

    # Social handles
    handles = SOCIAL_HANDLE.findall(result)
    if handles:
        found.append(f"social handle ({len(handles)} found)")
        result = SOCIAL_HANDLE.sub("[handle removed]", result)

    # English name reveals
    if NAME_REVEAL_EN.search(result):
        found.append("name reveal (english)")
        result = NAME_REVEAL_EN.sub(
            lambda m: m.group(0).replace(m.group(1), "[name removed]"),
            result
        )

    # Bengali name reveals
    if NAME_REVEAL_BN.search(result):
        found.append("name reveal (bengali)")
        result = NAME_REVEAL_BN.sub("[name removed]", result)

    return result, found


async def _claude_scrub(text: str) -> tuple[str, bool]:
    """
    Second pass — Claude catches edge cases regex misses.
    Only called if message is long enough to contain PII risk (>20 chars).
    Costs ~0.001 USD per message — acceptable for a portfolio demo.
    """
    client = anthropic.AsyncAnthropic()

    prompt = f"""You are a privacy scrubber for an anonymous blood donor chat system in Bangladesh.

Scrub any personally identifying information from this message:
- Phone numbers (Bangladesh format: 01XXXXXXXXX)
- Real names
- Email addresses  
- Home addresses
- Any other info that could identify the person

Replace removed content with [removed].
If nothing needs removing, return the message exactly as-is.
Return ONLY the scrubbed message, no explanation.

Message: {text}"""

    message = await client.messages.create(
        model      = "claude-haiku-4-5-20251001",
        max_tokens = 500,
        messages   = [{"role": "user", "content": prompt}],
    )

    scrubbed = message.content[0].text.strip()
    pii_found = scrubbed != text

    return scrubbed, pii_found


async def scrub_message(text: str, use_claude: bool = True) -> ScrubResult:
    """
    Full scrubbing pipeline — regex first, Claude second.

    Args:
        text:       Raw message from donor or requester
        use_claude: Whether to run Claude pass (disable in tests)

    Returns:
        ScrubResult with scrubbed text and metadata
    """
    if not text or not text.strip():
        return ScrubResult(
            original     = text,
            scrubbed     = text,
            pii_detected = False,
            items_found  = [],
        )

    # Pass 1 — regex (fast, free)
    after_regex, found = _regex_scrub(text)

    # Pass 2 — Claude (smart, catches Banglish edge cases)
    # Only run if message is substantial and Claude is enabled
    after_claude = after_regex
    claude_found_pii = False

    if use_claude and len(text) > 20:
        after_claude, claude_found_pii = await _claude_scrub(after_regex)
        if claude_found_pii and after_claude != after_regex:
            found.append("pii detected by claude")

    pii_detected = bool(found) or claude_found_pii

    return ScrubResult(
        original     = text,
        scrubbed     = after_claude,
        pii_detected = pii_detected,
        items_found  = found,
    )