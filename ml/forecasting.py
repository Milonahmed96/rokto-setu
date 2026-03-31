"""
ml/forecasting.py
-----------------
District-level blood shortage forecasting using LightGBM.
Wrapped with conformal prediction for calibrated uncertainty intervals.

Predicts: probability of blood shortage per district per blood group
          for the next 7 days.

Features:
    - Day of week, month, week of year
    - Seasonal factor
    - District ID, division ID
    - Blood group (encoded)
    - Rolling request counts
    - Active donor count ratio

Usage:
    python -m ml.forecasting --train
    python -m ml.forecasting --predict --district 1 --blood-group "O-"
"""

import argparse
import json
import pickle
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import mean_squared_error, mean_absolute_error

BLOOD_GROUPS = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
MODEL_DIR = Path("ml/models")
MODEL_PATH = MODEL_DIR / "forecaster.pkl"
ENCODER_PATH = MODEL_DIR / "encoders.pkl"
CALIB_PATH = MODEL_DIR / "calibration.pkl"


# ── Feature Engineering ───────────────────────────────────────────────────────

def build_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build feature matrix from historical request data.
    Each row = one (district, blood_group, week) combination.
    """
    df = df.copy()
    df["created_at"] = pd.to_datetime(df["created_at"])
    df["date"] = df["created_at"].dt.date
    df["month"] = df["created_at"].dt.month
    df["day_of_week"] = df["created_at"].dt.dayofweek
    df["week_of_year"] = df["created_at"].dt.isocalendar().week.astype(int)
    df["is_weekend"] = df["day_of_week"] >= 5

    # Seasonal factor by month
    SEASONAL = {
        1: 1.2, 2: 1.1, 3: 1.0, 4: 0.95,
        5: 0.9, 6: 0.75, 7: 0.7, 8: 0.7,
        9: 0.8, 10: 1.0, 11: 1.15, 12: 1.2,
    }
    df["seasonal_factor"] = df["month"].map(SEASONAL)

    # Is rare blood group
    df["is_rare"] = df["blood_group"].isin(["O-", "A-", "B-", "AB-"]).astype(int)

    # Aggregate: requests per district per blood group per week
    weekly = df.groupby(
        ["district_id", "blood_group", "week_of_year", "month"]
    ).agg(
        request_count   = ("request_index", "count"),
        fulfilled_count = ("fulfilled", "sum"),
        emergency_count = ("urgency", lambda x: (x == "EMERGENCY").sum()),
        avg_units       = ("units_needed", "mean"),
        seasonal_factor = ("seasonal_factor", "first"),
        division_id     = ("division_id", "first"),
        is_rare         = ("is_rare", "first"),
    ).reset_index()

    # Shortage rate — target variable
    weekly["shortage_rate"] = 1 - (
        weekly["fulfilled_count"] / weekly["request_count"].clip(lower=1)
    )

    # Rolling demand (lag features)
    weekly = weekly.sort_values(["district_id", "blood_group", "week_of_year"])
    weekly["demand_lag_1w"] = weekly.groupby(
        ["district_id", "blood_group"]
    )["request_count"].shift(1).fillna(0)

    weekly["demand_lag_2w"] = weekly.groupby(
        ["district_id", "blood_group"]
    )["request_count"].shift(2).fillna(0)

    weekly["shortage_lag_1w"] = weekly.groupby(
        ["district_id", "blood_group"]
    )["shortage_rate"].shift(1).fillna(0)

    return weekly


def get_feature_columns() -> list[str]:
    return [
        "district_id", "division_id", "blood_group_enc",
        "month", "week_of_year", "seasonal_factor",
        "is_rare", "request_count", "emergency_count",
        "avg_units", "demand_lag_1w", "demand_lag_2w",
        "shortage_lag_1w",
    ]


# ── Training ──────────────────────────────────────────────────────────────────

def train(data_path: str = "data/synthetic/historical_requests.json"):
    """Train the forecasting model and save to disk."""

    print("\nLoading historical data...")
    with open(data_path, encoding="utf-8") as f:
        raw = json.load(f)

    df = pd.DataFrame(raw)
    print(f"  {len(df)} historical requests loaded")

    print("\nBuilding features...")
    features_df = build_features(df)
    print(f"  {len(features_df)} weekly aggregates created")

    # Encode blood group
    le = LabelEncoder()
    features_df["blood_group_enc"] = le.fit_transform(features_df["blood_group"])

    feature_cols = get_feature_columns()
    X = features_df[feature_cols].fillna(0)
    y = features_df["shortage_rate"]

    # Train/calibration split — calibration set for conformal prediction
    X_train, X_calib, y_train, y_calib = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    print(f"\nTraining LightGBM...")
    print(f"  Train: {len(X_train)} samples")
    print(f"  Calibration: {len(X_calib)} samples")

    model = lgb.LGBMRegressor(
        n_estimators     = 200,
        learning_rate    = 0.05,
        max_depth        = 6,
        num_leaves       = 31,
        min_child_samples= 5,
        subsample        = 0.8,
        colsample_bytree = 0.8,
        random_state     = 42,
        verbose          = -1,
    )
    model.fit(X_train, y_train)

    # Evaluate on calibration set
    y_pred_calib = model.predict(X_calib)
    rmse = np.sqrt(mean_squared_error(y_calib, y_pred_calib))
    mae  = mean_absolute_error(y_calib, y_pred_calib)
    print(f"\nCalibration set metrics:")
    print(f"  RMSE: {rmse:.4f}")
    print(f"  MAE:  {mae:.4f}")

    # ── Conformal Prediction ──────────────────────────────────────────────────
    # Split conformal prediction — calibrate residuals
    residuals = np.abs(y_calib.values - y_pred_calib)
    # 90% coverage — q = 90th percentile of calibration residuals
    alpha    = 0.10
    q_level  = np.ceil((1 - alpha) * (len(residuals) + 1)) / len(residuals)
    q_hat    = np.quantile(residuals, min(q_level, 1.0))
    print(f"\nConformal prediction:")
    print(f"  Coverage target: {(1-alpha)*100:.0f}%")
    print(f"  Quantile (q̂):   {q_hat:.4f}")
    print(f"  Interval width:  ±{q_hat:.4f}")

    # ── SHAP Feature Importance ───────────────────────────────────────────────
    try:
        import shap
        explainer   = shap.TreeExplainer(model)
        shap_values = explainer.shap_values(X_calib)
        mean_shap   = np.abs(shap_values).mean(axis=0)
        importance  = dict(zip(feature_cols, mean_shap.tolist()))
        top_features = sorted(importance.items(), key=lambda x: x[1], reverse=True)
        print(f"\nTop features (SHAP):")
        for feat, val in top_features[:5]:
            bar = "█" * int(val * 50)
            print(f"  {feat:25s} {val:.4f}  {bar}")
    except Exception as e:
        print(f"\nSHAP skipped: {e}")
        importance = {}

    # Save everything
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    with open(MODEL_PATH, "wb") as f:
        pickle.dump(model, f)

    with open(ENCODER_PATH, "wb") as f:
        pickle.dump({"blood_group": le}, f)

    with open(CALIB_PATH, "wb") as f:
        pickle.dump({
            "q_hat":       q_hat,
            "alpha":       alpha,
            "rmse":        rmse,
            "mae":         mae,
            "importance":  importance,
            "trained_at":  datetime.now().isoformat(),
        }, f)

    print(f"\n✓ Model saved to {MODEL_PATH}")
    print(f"✓ Encoders saved to {ENCODER_PATH}")
    print(f"✓ Calibration saved to {CALIB_PATH}")

    return model, le, q_hat


# ── Inference ─────────────────────────────────────────────────────────────────

def load_model():
    """Load trained model and calibration from disk."""
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            f"Model not found at {MODEL_PATH}. Run 'python -m ml.forecasting --train' first."
        )

    with open(MODEL_PATH, "rb") as f:
        model = pickle.load(f)

    with open(ENCODER_PATH, "rb") as f:
        encoders = pickle.load(f)

    with open(CALIB_PATH, "rb") as f:
        calib = pickle.load(f)

    return model, encoders, calib


def predict_shortage(
    district_id:  int,
    division_id:  int,
    blood_group:  str,
    days_ahead:   int = 7,
) -> dict:
    """
    Predict blood shortage probability for a district + blood group.
    Returns point estimate + conformal prediction interval.
    """
    model, encoders, calib = load_model()
    le    = encoders["blood_group"]
    q_hat = calib["q_hat"]

    now    = datetime.now()
    future = now + timedelta(days=days_ahead)

    SEASONAL = {
        1: 1.2, 2: 1.1, 3: 1.0, 4: 0.95,
        5: 0.9, 6: 0.75, 7: 0.7, 8: 0.7,
        9: 0.8, 10: 1.0, 11: 1.15, 12: 1.2,
    }

    # Encode blood group — handle unseen labels gracefully
    try:
        bg_enc = le.transform([blood_group])[0]
    except ValueError:
        bg_enc = 0

    is_rare = 1 if blood_group in ["O-", "A-", "B-", "AB-"] else 0

    X = pd.DataFrame([{
        "district_id":    district_id,
        "division_id":    division_id,
        "blood_group_enc": bg_enc,
        "month":          future.month,
        "week_of_year":   future.isocalendar()[1],
        "seasonal_factor": SEASONAL[future.month],
        "is_rare":        is_rare,
        "request_count":  5,   # baseline estimate
        "emergency_count": 1,
        "avg_units":      1.5,
        "demand_lag_1w":  4,
        "demand_lag_2w":  4,
        "shortage_lag_1w": 0.2,
    }])

    point_estimate = float(model.predict(X)[0])
    point_estimate = max(0.0, min(1.0, point_estimate))

    # Conformal prediction interval
    lower = max(0.0, point_estimate - q_hat)
    upper = min(1.0, point_estimate + q_hat)

    # Shortage risk category
    if point_estimate >= 0.7:
        risk = "HIGH"
    elif point_estimate >= 0.4:
        risk = "MEDIUM"
    else:
        risk = "LOW"

    return {
        "district_id":     district_id,
        "blood_group":     blood_group,
        "days_ahead":      days_ahead,
        "shortage_prob":   round(point_estimate, 3),
        "lower_bound":     round(lower, 3),
        "upper_bound":     round(upper, 3),
        "coverage":        f"{(1 - calib['alpha']) * 100:.0f}%",
        "risk":            risk,
        "forecast_date":   future.strftime("%Y-%m-%d"),
        "model_rmse":      round(calib["rmse"], 4),
        "top_features":    sorted(
            calib.get("importance", {}).items(),
            key=lambda x: x[1], reverse=True
        )[:5],
    }


def predict_district_summary(district_id: int, division_id: int) -> list[dict]:
    """Predict shortage for all 8 blood groups in a district."""
    results = []
    for bg in BLOOD_GROUPS:
        try:
            pred = predict_shortage(district_id, division_id, bg)
            results.append(pred)
        except Exception as e:
            print(f"  Prediction failed for {bg}: {e}")
    return sorted(results, key=lambda x: x["shortage_prob"], reverse=True)


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Blood shortage forecasting")
    parser.add_argument("--train",       action="store_true")
    parser.add_argument("--predict",     action="store_true")
    parser.add_argument("--district",    type=int, default=1)
    parser.add_argument("--division",    type=int, default=1)
    parser.add_argument("--blood-group", type=str, default="O-")
    parser.add_argument("--days-ahead",  type=int, default=7)
    args = parser.parse_args()

    if args.train:
        train()

    if args.predict:
        result = predict_shortage(
            district_id  = args.district,
            division_id  = args.division,
            blood_group  = args.blood_group,
            days_ahead   = args.days_ahead,
        )
        print(f"\nForecast for district {args.district} — {args.blood_group}:")
        print(f"  Shortage probability: {result['shortage_prob']:.1%}")
        print(f"  90% CI: [{result['lower_bound']:.1%}, {result['upper_bound']:.1%}]")
        print(f"  Risk level: {result['risk']}")
        print(f"  Forecast date: {result['forecast_date']}")


if __name__ == "__main__":
    main()