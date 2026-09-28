from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_signup_and_login():
    client.post("/auth/signup", json={
        "name": "Integration User",
        "email": "saloni_test@example.com",
        "password": "Password123!"
    })
    res = client.post("/auth/login", data={"username": "saloni_test@example.com", "password": "Password123!"})
    assert res.status_code == 200
    assert "access_token" in res.json()

def test_multi_test_booking_workflow():
    login_res = client.post("/auth/login", data={"username": "saloni_test@example.com", "password": "Password123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Book MULTIPLE tests at once (IDs 1 & 2)
    booking_res = client.post("/bookings/", json={
        "centre_id": 1,
        "test_ids": [1, 2],
        "appointment_time": "2026-10-10T11:00:00"
    }, headers=headers)

    assert booking_res.status_code == 201
    data = booking_res.json()
    assert data["status"] == "PENDING"
    assert len(data["items"]) == 2
    assert data["total_amount"] > 0

def test_webhook_idempotency():
    login_res = client.post("/auth/login", data={"username": "saloni_test@example.com", "password": "Password123!"})
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    booking_res = client.post("/bookings/", json={
        "centre_id": 1,
        "test_ids": [1],
        "appointment_time": "2026-10-10T12:00:00"
    }, headers=headers)
    booking_id = booking_res.json()["id"]

    webhook_payload = {
        "event_id": f"evt_dup_check_{booking_id}",
        "booking_id": booking_id,
        "status": "SUCCESS"
    }

    # 1st call -> processed
    res1 = client.post("/payments/webhook/", json=webhook_payload)
    assert res1.status_code == 200
    assert res1.json()["booking_status"] == "CONFIRMED"

    # 2nd call with identical event_id -> idempotent duplicate caught
    res2 = client.post("/payments/webhook/", json=webhook_payload)
    assert res2.status_code == 200
    assert "already processed" in res2.json()["message"]
    assert res2.json()["status"] == "DUPLICATE_IGNORED"