import os
import uuid

import httpx

from otp_helper import get_register_otp


BASE_URL = os.getenv("TEST_API_URL", "http://localhost:6969/api")


def _auth_header():
    email = f"task-{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPass123"
    register = httpx.post(f"{BASE_URL}/auth/register", json={"email": email, "password": password, "role": "client"}, timeout=30)
    assert register.status_code == 200
    otp = get_register_otp(email, register.json()["data"])
    httpx.post(f"{BASE_URL}/auth/verify-otp", json={"email": email, "code": otp}, timeout=30)
    login = httpx.post(f"{BASE_URL}/auth/login", json={"email": email, "password": password}, timeout=30)
    token = login.json()["data"]["accessToken"]
    return {"Authorization": f"Bearer {token}"}


def test_task_crud_and_match():
    headers = _auth_header()

    created = httpx.post(
        f"{BASE_URL}/tasks",
        headers=headers,
        json={
            "title": "Test task",
            "description": "Task description",
            "price": 25,
            "currency": "EUR",
            "latitude": 6.1319,
            "longitude": 1.2228,
            "status": "OPEN",
        },
        timeout=30,
    )
    assert created.status_code == 200
    payload = created.json()
    assert payload["success"] is True
    task_id = payload["data"]["id"]

    listed = httpx.get(f"{BASE_URL}/tasks", headers=headers, timeout=30)
    assert listed.status_code == 200
    assert listed.json()["success"] is True

    detail = httpx.get(f"{BASE_URL}/tasks/{task_id}", headers=headers, timeout=30)
    assert detail.status_code == 200
    assert detail.json()["success"] is True

    updated = httpx.patch(f"{BASE_URL}/tasks/{task_id}", headers=headers, json={"price": 30}, timeout=30)
    assert updated.status_code == 200
    assert updated.json()["success"] is True

    matched = httpx.post(
        f"{BASE_URL}/tasks/match",
        headers=headers,
        json={"latitude": 6.1319, "longitude": 1.2228, "radius_km": 10},
        timeout=30,
    )
    assert matched.status_code == 200
    assert matched.json()["success"] is True

    deleted = httpx.delete(f"{BASE_URL}/tasks/{task_id}", headers=headers, timeout=30)
    assert deleted.status_code == 200
    assert deleted.json()["success"] is True
