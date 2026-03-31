"""
tests/test_anomaly.py
---------------------
Tests for Isolation Forest anomaly detection.
"""

import pytest
import pickle
from pathlib import Path
from ml.anomaly import (
    extract_features,
    score_request,
    generate_normal_requests,
    generate_anomalous_requests,
    ANOMALY_THRESHOLD,
)


# ── Model file tests ──────────────────────────────────────────────────────────

class TestModelFiles:

    def test_model_file_exists(self):
        assert Path("ml/models/anomaly_detector.pkl").exists()

    def test_scaler_file_exists(self):
        assert Path("ml/models/anomaly_scaler.pkl").exists()

    def test_meta_file_exists(self):
        assert Path("ml/models/anomaly_meta.pkl").exists()

    def test_meta_has_required_keys(self):
        with open("ml/models/anomaly_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        assert "threshold" in meta
        assert "trained_at" in meta
        assert "normal_precision" in meta
        assert "anomaly_recall" in meta

    def test_threshold_is_valid(self):
        with open("ml/models/anomaly_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        assert 0 < meta["threshold"] < 1

    def test_normal_precision_is_high(self):
        """Normal requests should be classified with high precision."""
        with open("ml/models/anomaly_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        assert meta["normal_precision"] >= 0.7


# ── Feature extraction tests ──────────────────────────────────────────────────

class TestFeatureExtraction:

    def test_extract_returns_dict(self):
        request = {
            "units_needed": 2, "urgency": "URGENT",
            "blood_group": "O+", "district_id": 1,
            "division_id": 1, "hour_of_day": 10,
            "is_weekend": False, "requests_last_hour": 0,
            "requests_last_day": 1, "same_location_reqs": 0,
        }
        result = extract_features(request)
        assert isinstance(result, dict)

    def test_extract_has_all_features(self):
        request = {"units_needed": 1, "urgency": "URGENT", "blood_group": "O+"}
        result = extract_features(request)
        assert "units_needed" in result
        assert "urgency_score" in result
        assert "blood_rarity" in result
        assert "hour_of_day" in result
        assert "requests_last_hour" in result

    def test_emergency_higher_urgency_score(self):
        emergency = extract_features({"urgency": "EMERGENCY"})
        planned   = extract_features({"urgency": "PLANNED"})
        assert emergency["urgency_score"] > planned["urgency_score"]

    def test_rare_blood_higher_rarity(self):
        rare   = extract_features({"blood_group": "AB-"})
        common = extract_features({"blood_group": "O+"})
        assert rare["blood_rarity"] > common["blood_rarity"]

    def test_defaults_for_missing_fields(self):
        result = extract_features({})
        assert result["units_needed"] == 1
        assert result["requests_last_hour"] == 0
        assert result["requests_last_day"] == 0


# ── Scoring tests ─────────────────────────────────────────────────────────────

class TestScoring:

    def _normal_request(self):
        return {
            "units_needed": 1, "urgency": "URGENT",
            "blood_group": "A+", "district_id": 5,
            "division_id": 2, "hour_of_day": 14,
            "is_weekend": False, "requests_last_hour": 0,
            "requests_last_day": 1, "same_location_reqs": 0,
        }

    def _suspicious_request(self):
        return {
            "units_needed": 2, "urgency": "EMERGENCY",
            "blood_group": "O-", "district_id": 1,
            "division_id": 1, "hour_of_day": 3,
            "is_weekend": False, "requests_last_hour": 6,
            "requests_last_day": 15, "same_location_reqs": 5,
        }

    def test_score_returns_required_fields(self):
        result = score_request(self._normal_request())
        assert "anomaly_score" in result
        assert "threshold" in result
        assert "is_suspicious" in result
        assert "verdict" in result
        assert "risk_factors" in result

    def test_score_in_valid_range(self):
        result = score_request(self._normal_request())
        assert 0.0 <= result["anomaly_score"] <= 1.0

    def test_normal_request_not_flagged(self):
        result = score_request(self._normal_request())
        assert result["verdict"] == "NORMAL"
        assert result["is_suspicious"] is False

    def test_suspicious_request_flagged(self):
        result = score_request(self._suspicious_request())
        assert result["verdict"] == "QUARANTINE"
        assert result["is_suspicious"] is True

    def test_suspicious_has_risk_factors(self):
        result = score_request(self._suspicious_request())
        assert len(result["risk_factors"]) > 0

    def test_normal_lower_score_than_suspicious(self):
        normal     = score_request(self._normal_request())
        suspicious = score_request(self._suspicious_request())
        assert normal["anomaly_score"] < suspicious["anomaly_score"]

    def test_threshold_matches_meta(self):
        with open("ml/models/anomaly_meta.pkl", "rb") as f:
            meta = pickle.load(f)
        result = score_request(self._normal_request())
        assert result["threshold"] == meta["threshold"]

    def test_verdict_consistent_with_score(self):
        result = score_request(self._normal_request())
        if result["anomaly_score"] > ANOMALY_THRESHOLD:
            assert result["verdict"] == "QUARANTINE"
        else:
            assert result["verdict"] == "NORMAL"

    def test_high_frequency_flagged(self):
        request = self._normal_request()
        request["requests_last_hour"] = 8
        request["requests_last_day"]  = 20
        result = score_request(request)
        assert any("frequency" in r.lower() or "request" in r.lower()
                   for r in result["risk_factors"])

    def test_unusual_hour_noted(self):
        request = self._normal_request()
        request["hour_of_day"] = 3
        request["requests_last_hour"] = 5
        request["requests_last_day"] = 12
        request["same_location_reqs"] = 4
        result = score_request(request)
        assert any("hour" in r.lower() or "AM" in r
                   for r in result["risk_factors"])


# ── Data generation tests ─────────────────────────────────────────────────────

class TestDataGeneration:

    def test_normal_requests_count(self):
        requests = generate_normal_requests(100)
        assert len(requests) == 100

    def test_anomalous_requests_count(self):
        requests = generate_anomalous_requests(50)
        assert len(requests) == 50

    def test_normal_requests_have_required_fields(self):
        requests = generate_normal_requests(10)
        for r in requests:
            assert "units_needed" in r
            assert "urgency" in r
            assert "blood_group" in r

    def test_normal_requests_reasonable_frequency(self):
        """Normal requests should not have high frequency."""
        requests = generate_normal_requests(100)
        high_freq = [r for r in requests if r["requests_last_hour"] > 3]
        assert len(high_freq) < 20  # less than 20% high frequency

    def test_anomalous_requests_high_frequency(self):
        """Anomalous requests should have suspicious patterns."""
        requests = generate_anomalous_requests(100)
        suspicious = [
            r for r in requests
            if r["requests_last_hour"] > 3 or r["requests_last_day"] > 5
        ]
        assert len(suspicious) > 30  # majority should be suspicious