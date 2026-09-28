import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

# 1. Test Centres & Initial Seeding
def test_get_centres():
    response = client.get("/centres/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 2
    assert "name" in data[0]

def test_get_centre_details_not_found():
    response = client.get("/centres/99999")
    assert response.status_code == 404

# 2. Test User Auth & JWT Token Issuance
def test_signup_and_login():
    signup_payload = {
        "name": "Integration User",
        "email": "test_integration@example.com",
        "password": "Password123!"
    }
    signup_res = client.post("/auth/signup", json=signup_payload)
    assert signup_res.status_code in [201, 400]

    login_res = client.post(
        "/auth/login",
        data={"username": "test_integration@example.com", "password": "Password123!"}
    )
    assert login_res.status_code == 200
    token_data = login_res.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"

# 3. Test Booking Workflow
def test_booking_workflow():
    login_res = client.post(
        "/auth/login",
        data={"username": "test_integration@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    booking_payload = {
        "centre_id": 1,
        "test_id": 1,
        "appointment_time": "2026-10-05T14:30:00"
    }
    booking_res = client.post("/bookings/", json=booking_payload, headers=headers)
    assert booking_res.status_code == 201
    booking_data = booking_res.json()
    assert booking_data["status"] == "PENDING"
    booking_id = booking_data["id"]

    list_res = client.get("/bookings/", headers=headers)
    assert list_res.status_code == 200
    assert any(b["id"] == booking_id for b in list_res.json())

# 4. Test Webhook Processing & Idempotency
def test_webhook_idempotency():
    login_res = client.post(
        "/auth/login",
        data={"username": "test_integration@example.com", "password": "Password123!"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    booking_res = client.post("/bookings/", json={
        "centre_id": 1,
        "test_id": 1,
        "appointment_time": "2026-10-06T10:00:00"
    }, headers=headers)
    booking_id = booking_res.json()["id"]

    webhook_payload = {
        "event_id": f"evt_unique_{booking_id}",
        "booking_id": booking_id,
        "status": "SUCCESS"
    }

    # First webhook call -> Processes and confirms booking
    res1 = client.post("/payments/webhook/", json=webhook_payload)
    assert res1.status_code == 200
    assert res1.json()["booking_status"] == "CONFIRMED"

    # Second call with identical payload -> Idempotency guard activates
    res2 = client.post("/payments/webhook/", json=webhook_payload)
    assert res2.status_code == 200
    assert "already processed" in res2.json()["message"]