import pytest
from httpx import AsyncClient, ASGITransport
from api.main import app


@pytest.mark.asyncio
async def test_register_invalid_phone():
    """Should reject non-Bangladesh phone numbers."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/register", json={
            "phone": "12345",
            "blood_group": "O-",
        })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_register_invalid_blood_group():
    """Should reject unknown blood groups."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/register", json={
            "phone": "01711123456",
            "blood_group": "Z+",
        })
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_verify_otp_wrong_otp():
    """Should reject incorrect OTP."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/verify-otp", json={
            "phone": "01711999999",
            "otp": "000000",
        })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_verify_otp_no_otp_requested():
    """Should return 400 if no OTP was requested for this number."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post("/auth/verify-otp", json={
            "phone": "01799999999",
            "otp": "123456",
        })
    assert response.status_code == 400
    assert "No OTP found" in response.json()["detail"]