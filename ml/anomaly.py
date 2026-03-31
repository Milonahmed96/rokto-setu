"""
ml/anomaly.py
-------------
Fake blood request detection using Isolation Forest.

Detects suspicious patterns:
- Multiple requests in a short time window (spam)
- Requests with implausible location patterns
- Abnormal units requested
- Unusual urgency patterns

Trained on synthetic normal request patterns.
Anomaly score > threshold → request quarantined for review.

Usage:
    python -m ml.anomaly --train
    python -m ml.anomaly --score
"""

import argparse
import json
import pickle
from pathlib import Path
from datetime import datetime

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report

MODEL_DIR  = Path("ml/models")
ANOM_MODEL = MODEL_DIR / "anomaly_detector.pkl"
ANOM_SCALER = MODEL_DIR / "anomaly_scaler.pkl"
ANOM_META   = MODEL_DIR / "anomaly_meta.pkl"

ANOMALY_THRESHOLD = 0.75  # scores above this are flagged


# ── Feature Engineering ───────────────────────────────────────────────────────

def extract_features(request: dict) -> dict:
    """
    Extract anomaly detection features from a single blood request.
    All features are numeric — no raw text.
    """
    BLOOD_GROUP_RARITY = {
        "O+": 1, "A+": 2, "B+": 3, "AB+": 4,
        "O-": 5, "A-": 6, "B-": 7, "AB-": 8,
    }
    URGENCY_SCORE = {
        "PLANNED": 1, "URGENT": 2, "EMERGENCY": 3,
    }

    return {
        "units_needed":    request.get("units_needed", 1),
        "urgency_score":   URGENCY_SCORE.get(request.get("urgency", "URGENT"), 2),
        "blood_rarity":    BLOOD_GROUP_RARITY.get(request.get("blood_group", "O+"), 1),
        "district_id":     request.get("district_id", 1),
        "division_id":     request.get("division_id", 1),
        "hour_of_day":     request.get("hour_of_day", 12),
        "is_weekend":      int(request.get("is_weekend", False)),
        "requests_last_hour":  request.get("requests_last_hour", 0),
        "requests_last_day":   request.get("requests_last_day", 0),
        "same_location_reqs":  request.get("same_location_reqs", 0),
    }


def build_training_features(
    normal_requests: list[dict],
    anomalous_requests: list[dict],
) -> tuple[np.ndarray, np.ndarray]:
    """Build feature matrix from normal and anomalous requests."""

    normal_features = [extract_features(r) for r in normal_requests]
    anomaly_features = [extract_features(r) for r in anomalous_requests]

    all_features = normal_features + anomaly_features
    labels = [0] * len(normal_features) + [1] * len(anomaly_features)

    df = pd.DataFrame(all_features)
    return df.values, np.array(labels)


# ── Synthetic Abuse Patterns ───────────────────────────────────────────────────

def generate_normal_requests(count: int = 1000) -> list[dict]:
    """Generate realistic normal blood requests."""
    import random
    requests = []
    for _ in range(count):
        requests.append({
            "units_needed":       random.choices([1, 2, 3], weights=[60, 30, 10])[0],
            "urgency":            random.choices(
                ["PLANNED", "URGENT", "EMERGENCY"],
                weights=[25, 45, 30]
            )[0],
            "blood_group":        random.choices(
                ["O+", "A+", "B+", "AB+", "O-", "A-", "B-", "AB-"],
                weights=[37, 28, 22, 7, 2, 2, 1, 1]
            )[0],
            "district_id":        random.randint(1, 20),
            "division_id":        random.randint(1, 8),
            "hour_of_day":        random.choices(
                range(24),
                weights=[1,1,1,1,1,2,3,4,5,5,5,5,5,5,5,5,5,4,4,4,3,3,2,1]
            )[0],
            "is_weekend":         random.random() < 0.28,
            "requests_last_hour": random.choices([0, 1], weights=[90, 10])[0],
            "requests_last_day":  random.choices([0, 1, 2], weights=[70, 25, 5])[0],
            "same_location_reqs": random.choices([0, 1], weights=[85, 15])[0],
        })
    return requests


def generate_anomalous_requests(count: int = 200) -> list[dict]:
    """Generate anomalous/fake request patterns."""
    import random
    requests = []

    patterns = [
        # Pattern 1: Spam — many requests in short time
        lambda: {
            "units_needed":       random.randint(1, 2),
            "urgency":            "EMERGENCY",
            "blood_group":        "O-",
            "district_id":        random.randint(1, 5),
            "division_id":        1,
            "hour_of_day":        random.randint(0, 23),
            "is_weekend":         False,
            "requests_last_hour": random.randint(4, 15),
            "requests_last_day":  random.randint(8, 30),
            "same_location_reqs": random.randint(3, 10),
        },
        # Pattern 2: Implausible units
        lambda: {
            "units_needed":       random.randint(8, 10),
            "urgency":            "EMERGENCY",
            "blood_group":        random.choice(["O-", "AB-"]),
            "district_id":        random.randint(1, 20),
            "division_id":        random.randint(1, 8),
            "hour_of_day":        random.randint(0, 23),
            "is_weekend":         False,
            "requests_last_hour": random.randint(2, 8),
            "requests_last_day":  random.randint(5, 20),
            "same_location_reqs": random.randint(2, 6),
        },
        # Pattern 3: Repeated same-location requests
        lambda: {
            "units_needed":       1,
            "urgency":            random.choice(["URGENT", "EMERGENCY"]),
            "blood_group":        "O+",
            "district_id":        1,
            "division_id":        1,
            "hour_of_day":        3,   # 3 AM — suspicious
            "is_weekend":         True,
            "requests_last_hour": random.randint(3, 8),
            "requests_last_day":  random.randint(6, 15),
            "same_location_reqs": random.randint(4, 12),
        },
    ]

    for _ in range(count):
        pattern = random.choice(patterns)
        requests.append(pattern())

    return requests


# ── Training ──────────────────────────────────────────────────────────────────

def train():
    """Train Isolation Forest on normal + anomalous request patterns."""
    print("\nGenerating training data...")
    normal    = generate_normal_requests(1000)
    anomalous = generate_anomalous_requests(200)

    print(f"  Normal requests:    {len(normal)}")
    print(f"  Anomalous requests: {len(anomalous)}")

    X, y = build_training_features(normal, anomalous)

    # Scale features
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    print("\nTraining Isolation Forest...")
    model = IsolationForest(
        n_estimators     = 200,
        contamination    = 0.15,  # ~15% anomaly rate in training
        max_samples      = "auto",
        random_state     = 42,
        n_jobs           = -1,
    )
    model.fit(X_scaled)

    # Evaluate — convert IF scores to anomaly probability
    raw_scores = model.score_samples(X_scaled)
    # Isolation Forest: more negative = more anomalous
    # Normalise to 0-1 where 1 = most anomalous
    normalised = 1 - (raw_scores - raw_scores.min()) / (
        raw_scores.max() - raw_scores.min() + 1e-10
    )

    # Threshold evaluation
    predicted = (normalised > ANOMALY_THRESHOLD).astype(int)
    print("\nClassification report:")
    report = classification_report(
        y, predicted,
        target_names=["normal", "anomalous"],
        output_dict=True,
    )
    print(classification_report(y, predicted, target_names=["normal", "anomalous"]))

    # Save
    MODEL_DIR.mkdir(parents=True, exist_ok=True)

    with open(ANOM_MODEL, "wb") as f:
        pickle.dump(model, f)

    with open(ANOM_SCALER, "wb") as f:
        pickle.dump(scaler, f)

    with open(ANOM_META, "wb") as f:
        pickle.dump({
            "threshold":          ANOMALY_THRESHOLD,
            "contamination":      0.15,
            "n_estimators":       200,
            "normal_precision":   report["normal"]["precision"],
            "anomaly_recall":     report["anomalous"]["recall"],
            "trained_at":         datetime.now().isoformat(),
        }, f)

    print(f"✓ Anomaly detector saved to {ANOM_MODEL}")
    return model, scaler


# ── Inference ─────────────────────────────────────────────────────────────────

def load_anomaly_model():
    if not ANOM_MODEL.exists():
        raise FileNotFoundError(
            "Anomaly model not found. Run 'python -m ml.anomaly --train' first."
        )
    with open(ANOM_MODEL, "rb") as f:
        model = pickle.load(f)
    with open(ANOM_SCALER, "rb") as f:
        scaler = pickle.load(f)
    with open(ANOM_META, "rb") as f:
        meta = pickle.load(f)
    return model, scaler, meta


def score_request(request: dict) -> dict:
    """
    Score a single blood request for anomaly.
    Returns anomaly score 0-1 and verdict.
    """
    model, scaler, meta = load_anomaly_model()

    features = extract_features(request)
    X = pd.DataFrame([features])
    X_scaled = scaler.transform(X.values)

    raw_score  = model.score_samples(X_scaled)[0]

    # Normalise — we use fixed min/max from training distribution
    # More negative raw score = more anomalous → higher normalised score
    normalised = float(np.clip((-raw_score - 0.1) / 0.5, 0, 1))

    threshold  = meta["threshold"]
    is_anomaly = normalised > threshold

    return {
        "anomaly_score":  round(normalised, 3),
        "threshold":      threshold,
        "is_suspicious":  is_anomaly,
        "verdict":        "QUARANTINE" if is_anomaly else "NORMAL",
        "risk_factors":   _explain_risk(request, normalised),
    }


def _explain_risk(request: dict, score: float) -> list[str]:
    """Simple rule-based explanation of why a request was flagged."""
    reasons = []

    if request.get("requests_last_hour", 0) >= 3:
        reasons.append(f"High request frequency: {request['requests_last_hour']} in last hour")

    if request.get("requests_last_day", 0) >= 6:
        reasons.append(f"Excessive daily requests: {request['requests_last_day']} today")

    if request.get("units_needed", 1) >= 7:
        reasons.append(f"Implausible units: {request['units_needed']} units requested")

    if request.get("same_location_reqs", 0) >= 3:
        reasons.append(f"Repeated same-location requests: {request['same_location_reqs']}")

    if request.get("hour_of_day", 12) in range(1, 5):
        reasons.append(f"Unusual hour: {request['hour_of_day']}:00 AM")

    if score > 0.85:
        reasons.append("Overall pattern strongly deviates from normal requests")

    return reasons


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Anomaly detection for blood requests")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--score", action="store_true",
                        help="Score a test request")
    args = parser.parse_args()

    if args.train:
        train()

    if args.score:
        # Test with a suspicious request
        test_request = {
            "units_needed":       2,
            "urgency":            "EMERGENCY",
            "blood_group":        "O-",
            "district_id":        1,
            "division_id":        1,
            "hour_of_day":        3,
            "is_weekend":         False,
            "requests_last_hour": 5,
            "requests_last_day":  12,
            "same_location_reqs": 4,
        }
        result = score_request(test_request)
        print(f"\nAnomaly score: {result['anomaly_score']}")
        print(f"Verdict:       {result['verdict']}")
        print(f"Risk factors:")
        for r in result["risk_factors"]:
            print(f"  • {r}")


if __name__ == "__main__":
    main()