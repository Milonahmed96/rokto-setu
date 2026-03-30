"""
tests/test_nlp.py
-----------------
Tests for PII scrubber and NLP request parser.
All tests run without Claude API calls (use_claude=False)
so CI doesn't need an API key for the NLP tests.
"""

import pytest
from nlp.scrubber import scrub_message, _regex_scrub
from nlp.parser import _quick_parse


# ── PII Scrubber — regex pass ─────────────────────────────────────────────────

class TestRegexScrubber:

    def test_bd_phone_standard(self):
        text = "Call me at 01711123456"
        result, found = _regex_scrub(text)
        assert "01711123456" not in result
        assert "[phone removed]" in result
        assert any("phone" in f for f in found)

    def test_bd_phone_with_dash(self):
        text = "My number is 017-11123456"
        result, found = _regex_scrub(text)
        assert "017-11123456" not in result
        assert any("phone" in f for f in found)

    def test_bd_phone_with_spaces(self):
        text = "reach me 0171 1123456"
        result, found = _regex_scrub(text)
        assert any("phone" in f for f in found)

    def test_email_removed(self):
        text = "email me at karim@gmail.com"
        result, found = _regex_scrub(text)
        assert "karim@gmail.com" not in result
        assert "[email removed]" in result
        assert any("email" in f for f in found)

    def test_url_removed(self):
        text = "Check https://wa.me/01711123456"
        result, found = _regex_scrub(text)
        assert "https://wa.me" not in result
        assert any("url" in f for f in found)

    def test_social_handle_removed(self):
        text = "Find me on @karim_dhaka"
        result, found = _regex_scrub(text)
        assert "@karim_dhaka" not in result
        assert any("handle" in f for f in found)

    def test_name_reveal_english(self):
        text = "My name is Karim Ahmed, I am coming"
        result, found = _regex_scrub(text)
        assert "Karim Ahmed" not in result
        assert any("name" in f for f in found)

    def test_name_reveal_i_am(self):
        text = "I am Rahim, arriving at 5pm"
        result, found = _regex_scrub(text)
        assert "Rahim" not in result

    def test_clean_message_unchanged(self):
        text = "I will arrive at DMCH ward 4 by 5pm today"
        result, found = _regex_scrub(text)
        assert result == text
        assert len(found) == 0

    def test_multiple_pii_items(self):
        text = "I am Karim, call 01711123456 or email k@gmail.com"
        result, found = _regex_scrub(text)
        assert "01711123456" not in result
        assert "k@gmail.com" not in result
        assert len(found) >= 2

    def test_empty_message(self):
        result, found = _regex_scrub("")
        assert result == ""
        assert found == []

    def test_bengali_name_reveal(self):
        text = "আমি করিম, আসছি"
        result, found = _regex_scrub(text)
        assert any("bengali" in f for f in found)

    def test_message_preserved_after_scrub(self):
        """Core info should survive scrubbing."""
        text = "arriving at DMCH ward 4, my number is 01711123456"
        result, found = _regex_scrub(text)
        assert "DMCH" in result
        assert "ward 4" in result
        assert "arriving" in result


# ── PII Scrubber — async full pipeline ───────────────────────────────────────

class TestScrubMessageAsync:

    @pytest.mark.asyncio
    async def test_phone_scrubbed_async(self):
        result = await scrub_message("call me 01799887766", use_claude=False)
        assert result.pii_detected is True
        assert "01799887766" not in result.scrubbed

    @pytest.mark.asyncio
    async def test_clean_message_async(self):
        result = await scrub_message(
            "I can arrive at Dhaka Medical by 6pm", use_claude=False
        )
        assert result.pii_detected is False
        assert result.scrubbed == "I can arrive at Dhaka Medical by 6pm"

    @pytest.mark.asyncio
    async def test_empty_message_async(self):
        result = await scrub_message("", use_claude=False)
        assert result.pii_detected is False
        assert result.scrubbed == ""

    @pytest.mark.asyncio
    async def test_scrub_result_fields(self):
        result = await scrub_message("my phone 01711000000", use_claude=False)
        assert hasattr(result, "original")
        assert hasattr(result, "scrubbed")
        assert hasattr(result, "pii_detected")
        assert hasattr(result, "items_found")
        assert result.original == "my phone 01711000000"


# ── NLP Parser — quick parse (regex, no API) ─────────────────────────────────

class TestQuickParser:

    def test_blood_group_o_neg(self):
        result = _quick_parse("need O- blood urgent")
        assert result.get("blood_group") == "O-"

    def test_blood_group_o_neg_written(self):
        result = _quick_parse("need O negative blood")
        assert result.get("blood_group") == "O-"

    def test_blood_group_ab_pos(self):
        result = _quick_parse("AB positive needed")
        assert result.get("blood_group") == "AB+"

    def test_blood_group_b_neg(self):
        result = _quick_parse("B- required for surgery")
        assert result.get("blood_group") == "B-"

    def test_units_extracted(self):
        result = _quick_parse("need 3 units O+ blood")
        assert result.get("units_needed") == 3

    def test_units_bags(self):
        result = _quick_parse("2 bags of A- needed")
        assert result.get("units_needed") == 2

    def test_urgency_emergency(self):
        result = _quick_parse("emergency O- needed now")
        assert result.get("urgency") == "EMERGENCY"

    def test_urgency_planned(self):
        result = _quick_parse("surgery tomorrow need B+")
        assert result.get("urgency") == "PLANNED"

    def test_urgency_urgent(self):
        """'urgent' should map to URGENT not EMERGENCY."""
        result = _quick_parse("urgent A+ needed today")
        assert result.get("urgency") == "URGENT"

    def test_no_blood_group(self):
        result = _quick_parse("need blood urgently")
        assert result.get("blood_group") is None

    def test_units_capped_at_10(self):
        result = _quick_parse("need 15 units O+")
        assert result.get("units_needed") == 10

    def test_bengali_urgency(self):
        """জরুরি maps to EMERGENCY."""
        result = _quick_parse("জরুরি O- রক্ত দরকার")
        assert result.get("urgency") == "EMERGENCY"

    def test_combined_extraction(self):
        result = _quick_parse("emergency 2 units O- DMCH today")
        assert result.get("blood_group") == "O-"
        assert result.get("units_needed") == 2
        assert result.get("urgency") in ("EMERGENCY", "URGENT")