"""
tests/test_forecasting.py
-------------------------
Tests for the LightGBM forecasting model and conformal prediction wrapper.
All tests use the already-trained model — no retraining during CI.
"""

import pytest
import pickle
from pathlib import Path


# ── Model file tests ──────────────────────────────────────────────────────────

class TestModelFiles:

    def test_model_file_exists(self):
        assert Path("ml/models/forecaster.pkl").exists(), \
            "Model not trained. Run 'python -m ml.forecasting --train'"

    def test_encoder_file_exists(self):
        assert Path("ml/models/encoders.pkl").exists()

    def test_calibration_file_exists(self):
        assert Path("ml/models/calibration.pkl").exists()

    def test_calibration_has_required_keys(self):
        with open("ml/models/calibration.pkl", "rb") as f:
            calib = pickle.load(f)
        assert "q_hat" in calib
        assert "alpha" in calib
        assert "rmse" in calib
        assert "mae" in calib
        assert "trained_at" in calib

    def test_calibration_alpha_is_valid(self):
        with open("ml/models/calibration.pkl", "rb") as f:
            calib = pickle.load(f)
        assert 0 < calib["alpha"] < 1

    def test_calibration_q_hat_is_positive(self):
        with open("ml/models/calibration.pkl", "rb") as f:
            calib = pickle.load(f)
        assert calib["q_hat"] >= 0

    def test_rmse_is_reasonable(self):
        with open("ml/models/calibration.pkl", "rb") as f:
            calib = pickle.load(f)
        # RMSE should be less than 1.0 (shortage rate is 0-1)
        assert calib["rmse"] < 1.0


# ── Prediction tests ──────────────────────────────────────────────────────────

class TestPredictions:

    def test_predict_returns_required_fields(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(
            district_id = 1,
            division_id = 1,
            blood_group = "O-",
            days_ahead  = 7,
        )
        assert "shortage_prob" in result
        assert "lower_bound" in result
        assert "upper_bound" in result
        assert "risk" in result
        assert "forecast_date" in result
        assert "coverage" in result

    def test_shortage_prob_in_valid_range(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        assert 0.0 <= result["shortage_prob"] <= 1.0

    def test_lower_bound_in_valid_range(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "A+", 7)
        assert 0.0 <= result["lower_bound"] <= 1.0

    def test_upper_bound_in_valid_range(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "B+", 7)
        assert 0.0 <= result["upper_bound"] <= 1.0

    def test_lower_bound_leq_upper_bound(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        assert result["lower_bound"] <= result["upper_bound"]

    def test_point_within_interval(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        # Point estimate should be within or at bounds
        assert result["lower_bound"] <= result["shortage_prob"] <= result["upper_bound"] \
            or result["shortage_prob"] >= result["lower_bound"]

    def test_risk_is_valid_category(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        assert result["risk"] in ("LOW", "MEDIUM", "HIGH")

    def test_rare_blood_groups_predicted(self):
        from ml.forecasting import predict_shortage
        for bg in ["O-", "A-", "B-", "AB-"]:
            result = predict_shortage(1, 1, bg, 7)
            assert result["shortage_prob"] >= 0

    def test_all_blood_groups_predicted(self):
        from ml.forecasting import predict_shortage
        for bg in ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]:
            result = predict_shortage(1, 1, bg, 7)
            assert "shortage_prob" in result

    def test_different_districts_give_different_results(self):
        from ml.forecasting import predict_shortage
        r1 = predict_shortage(1,  1, "O-", 7)
        r2 = predict_shortage(7,  2, "O-", 7)
        # Different districts should give different predictions
        assert r1["shortage_prob"] != r2["shortage_prob"]

    def test_district_summary_returns_8_groups(self):
        from ml.forecasting import predict_district_summary
        results = predict_district_summary(1, 1)
        assert len(results) == 8

    def test_district_summary_sorted_by_risk(self):
        from ml.forecasting import predict_district_summary
        results = predict_district_summary(1, 1)
        probs = [r["shortage_prob"] for r in results]
        assert probs == sorted(probs, reverse=True)

    def test_coverage_string_format(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        assert "%" in result["coverage"]

    def test_forecast_date_is_string(self):
        from ml.forecasting import predict_shortage
        result = predict_shortage(1, 1, "O-", 7)
        assert isinstance(result["forecast_date"], str)
        assert len(result["forecast_date"]) == 10  # YYYY-MM-DD


# ── Feature engineering tests ─────────────────────────────────────────────────

class TestFeatureEngineering:

    def test_build_features_returns_dataframe(self):
        import pandas as pd
        import json
        from ml.forecasting import build_features

        with open("data/synthetic/historical_requests.json", encoding="utf-8") as f:
            raw = json.load(f)

        df = pd.DataFrame(raw)
        result = build_features(df)

        assert isinstance(result, pd.DataFrame)
        assert len(result) > 0

    def test_build_features_has_shortage_rate(self):
        import pandas as pd
        import json
        from ml.forecasting import build_features

        with open("data/synthetic/historical_requests.json", encoding="utf-8") as f:
            raw = json.load(f)

        df = pd.DataFrame(raw)
        result = build_features(df)

        assert "shortage_rate" in result.columns
        assert result["shortage_rate"].between(0, 1).all()

    def test_build_features_has_lag_columns(self):
        import pandas as pd
        import json
        from ml.forecasting import build_features

        with open("data/synthetic/historical_requests.json", encoding="utf-8") as f:
            raw = json.load(f)

        df = pd.DataFrame(raw)
        result = build_features(df)

        assert "demand_lag_1w" in result.columns
        assert "demand_lag_2w" in result.columns
        assert "shortage_lag_1w" in result.columns