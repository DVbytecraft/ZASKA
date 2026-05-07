import os
import uuid

import httpx

from otp_helper import get_register_otp


BASE_URL = os.getenv("TEST_API_URL", "http://localhost:6969/api")


def _unique_email() -> str:
    return f"test+{uuid.uuid4().hex[:8]}@zaska-test.dev"


def _unique_phone() -> str:
    return f"+2289{uuid.uuid4().int % 10**7:07d}"


def test_auth_register_verify_login_refresh_logout():
    email = _unique_email()
    phone = _unique_phone()
    password = "StrongPass123"

    register = httpx.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "firstName": "Test",
            "lastName": "User",
            "phone": phone,
            "password": password,
            "role": "client",
        },
        timeout=30,
    )
    assert register.status_code == 200
    payload = register.json()
    assert payload["success"] is True

    otp = get_register_otp(email)

    verify = httpx.post(f"{BASE_URL}/auth/verify-otp", json={"email": email, "code": otp}, timeout=30)
    assert verify.status_code == 200
    verify_data = verify.json()
    assert verify_data["success"] is True
    assert "accessToken" in verify_data["data"]
    assert "refreshToken" in verify_data["data"]

    login = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert login.status_code == 200
    login_payload = login.json()
    assert login_payload["success"] is True
    refresh_token = login_payload["data"]["refreshToken"]

    refresh = httpx.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": refresh_token}, timeout=30)
    assert refresh.status_code == 200
    assert refresh.json()["success"] is True

    logout = httpx.post(f"{BASE_URL}/auth/logout", json={"refresh_token": refresh_token}, timeout=30)
    assert logout.status_code == 200
    assert logout.json()["success"] is True


def test_login_rejected_if_not_verified():
    email = _unique_email()
    phone = _unique_phone()
    password = "StrongPass123"

    httpx.post(
        f"{BASE_URL}/auth/register",
        json={
            "email": email,
            "firstName": "Test",
            "lastName": "Unverified",
            "phone": phone,
            "password": password,
            "role": "client",
        },
        timeout=30,
    )

    login = httpx.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": password},
        timeout=30,
    )
    assert login.status_code == 401
