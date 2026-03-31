"""
api/routes/anomaly.py
---------------------
Anomaly detection endpoint — scores blood requests for suspicious patterns.
Called automatically when a request is submitted.
Also exposed as a standalone endpoint for the demo dashboard.
"""

from typing import Annotated, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from api.routes.auth import get_current_user

router = APIRouter(prefix="/anomaly", tags=["anomaly"])


class AnomalyCheckRequest(BaseModel):
    units_needed:        int   = 1
    urgency:             str   = "URGENT"
    blood_group:         str   = "O+"
    district_id:         int   = 1
    division_id:         int   = 1
    hour_of_day:         int   = 12
    is_weekend:          bool  = False
    requests_last_hour:  int   = 0
    requests_last_day:   int   = 0
    same_location_reqs:  int   = 0


@router.post("/score")
async def score_request(
    body:         AnomalyCheckRequest,
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """
    Score a blood request for anomalous patterns.
    Returns anomaly score 0-1, verdict, and risk factor explanations.

    Demo endpoint — shows the Isolation Forest detector in action.
    """
    try:
        from ml.anomaly import score_request as _score
        result = _score(body.model_dump())
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly model not trained. Run 'python -m ml.anomaly --train' first.",
        )

    return result


@router.get("/model-info")
async def anomaly_model_info(
    current_user: Annotated[dict, Depends(get_current_user)],
):
    """Return anomaly detector metadata."""
    try:
        from ml.anomaly import load_anomaly_model
        _, _, meta = load_anomaly_model()
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Anomaly model not trained yet.",
        )

    return {
        "model_type":         "Isolation Forest",
        "n_estimators":       meta["n_estimators"],
        "contamination":      meta["contamination"],
        "threshold":          meta["threshold"],
        "normal_precision":   round(meta["normal_precision"], 3),
        "anomaly_recall":     round(meta["anomaly_recall"], 3),
        "trained_at":         meta["trained_at"],
        "description":        (
            "Detects suspicious blood request patterns — "
            "spam, implausible units, unusual timing, repeated same-location requests."
        ),
    }