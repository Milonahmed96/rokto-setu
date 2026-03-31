"""
api/routes/forecast.py
----------------------
Blood shortage forecasting endpoint.
Uses trained LightGBM model with conformal prediction intervals.
"""

from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status

from api.routes.auth import get_current_user

router = APIRouter(prefix="/forecast", tags=["forecast"])


@router.get("/district/{district_id}")
async def forecast_district(
    district_id:  int,
    division_id:  int = 1,
    days_ahead:   int = 7,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """
    Forecast blood shortage probability for all 8 blood groups
    in a given district over the next N days.

    Returns point estimates + 90% conformal prediction intervals + SHAP features.
    """
    try:
        from ml.forecasting import predict_district_summary
        results = predict_district_summary(district_id, division_id)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecasting model not trained yet. Run 'python -m ml.forecasting --train' first.",
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Forecast error: {str(e)}",
        )

    high_risk   = [r for r in results if r["risk"] == "HIGH"]
    medium_risk = [r for r in results if r["risk"] == "MEDIUM"]

    return {
        "district_id":   district_id,
        "division_id":   division_id,
        "days_ahead":    days_ahead,
        "forecast_date": results[0]["forecast_date"] if results else None,
        "coverage":      "90%",
        "summary": {
            "high_risk_groups":   [r["blood_group"] for r in high_risk],
            "medium_risk_groups": [r["blood_group"] for r in medium_risk],
            "alert_level":        "HIGH" if high_risk else "MEDIUM" if medium_risk else "LOW",
        },
        "predictions":   results,
        "model_info": {
            "type":     "LightGBM + Conformal Prediction",
            "coverage": "90% prediction intervals",
            "note":     "Trained on synthetic data — intervals widen with limited samples",
        },
    }


@router.get("/district/{district_id}/blood-group/{blood_group}")
async def forecast_single(
    district_id:  int,
    blood_group:  str,
    division_id:  int = 1,
    days_ahead:   int = 7,
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """
    Forecast shortage for a specific district + blood group combination.
    Used by the hospital dashboard for targeted monitoring.
    """
    valid_groups = ["A+", "A-", "B+", "B-", "O+", "O-", "AB+", "AB-"]
    if blood_group not in valid_groups:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid blood group. Must be one of: {valid_groups}",
        )

    try:
        from ml.forecasting import predict_shortage
        result = predict_shortage(
            district_id  = district_id,
            division_id  = division_id,
            blood_group  = blood_group,
            days_ahead   = days_ahead,
        )
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Forecasting model not trained yet.",
        )

    return result


@router.get("/model-info")
async def model_info(
    current_user: Annotated[dict, Depends(get_current_user)] = None,
):
    """Return model metadata — training metrics, feature importance, calibration."""
    try:
        from ml.forecasting import load_model
        _, _, calib = load_model()
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not trained yet.",
        )

    return {
        "model_type":     "LightGBM Regressor",
        "uncertainty":    "Split Conformal Prediction (90% coverage)",
        "rmse":           calib["rmse"],
        "mae":            calib["mae"],
        "q_hat":          calib["q_hat"],
        "coverage_target": f"{(1 - calib['alpha']) * 100:.0f}%",
        "trained_at":     calib["trained_at"],
        "top_features":   sorted(
            calib.get("importance", {}).items(),
            key=lambda x: x[1], reverse=True
        )[:8],
        "feature_note":   "SHAP mean absolute values — higher = more predictive",
    }