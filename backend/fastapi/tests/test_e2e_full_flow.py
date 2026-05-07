"""
End-to-end flow against a RUNNING API + Redis (Docker or local).
Run in backend container:
  docker compose exec -e TEST_API_URL=http://127.0.0.1:6969/api \\
    -e TEST_WS_URL=ws://127.0.0.1:6969 \\
    -e TEST_REDIS_URL=redis://redis:6379/0 \\
    backend sh -c "cd /app/backend/fastapi && pytest tests/test_e2e_full_flow.py -q"
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid

import httpx
import pytest
import websockets

from otp_helper import get_register_otp

BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:6969/api")
WS_ORIGIN = os.getenv("TEST_WS_URL", "ws://127.0.0.1:6969")


def _unique_email() -> str:
    return f"e2e+{uuid.uuid4().hex[:8]}@zaska-test.dev"


def _unique_phone() -> str:
    return f"+2289{uuid.uuid4().int % 10**7:07d}"


def _register_and_login() -> dict[str, str]:
    """Returns Authorization header dict with a valid access token."""
    email = _unique_email()
    phone = _unique_phone()
    pwd = "E2EPassStrong9!"
    with httpx.Client(timeout=45.0) as c:
        reg = c.post(
            f"{BASE_URL}/auth/register",
            json={
                "email": email,
                "firstName": "E2E",
                "lastName": "User",
                "phone": phone,
                "password": pwd,
                "role": "client",
            },
        )
        assert reg.status_code == 200, reg.text
        reg_js = reg.json()
        assert reg_js["success"] is True

        otp = get_register_otp(email)
        v = c.post(f"{BASE_URL}/auth/verify-otp", json={"email": email, "code": otp})
        assert v.status_code == 200

        lg = c.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd})
        assert lg.status_code == 200
        refresh_token = lg.json()["data"]["refreshToken"]

        rf = c.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": refresh_token})
        assert rf.status_code == 200
        rf_js = rf.json()
        assert rf_js["success"] is True
        access = rf_js["data"]["accessToken"]
        return {"Authorization": f"Bearer {access}"}


@pytest.mark.asyncio
async def test_full_flow_tasks_match_ws_chat_roundtrip():
    headers = _register_and_login()

    payload = {
        "title": "E2E task",
        "description": "End-to-end",
        "price": 42,
        "currency": "EUR",
        "latitude": 6.1319,
        "longitude": 1.2228,
        "status": "OPEN",
    }

    async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
        created = await client.post(f"{BASE_URL}/tasks", json=payload)
        assert created.status_code == 200, created.text
        cjs = created.json()
        assert cjs["success"] is True
        task_id = cjs["data"]["id"]

        listed = await client.get(f"{BASE_URL}/tasks")
        assert listed.status_code == 200
        assert listed.json()["success"] is True

        detail = await client.get(f"{BASE_URL}/tasks/{task_id}")
        assert detail.status_code == 200
        assert detail.json()["success"] is True

        patched = await client.patch(f"{BASE_URL}/tasks/{task_id}", json={"price": 44})
        assert patched.status_code == 200
        assert patched.json()["data"]["price"] == 44

        matched = await client.post(
            f"{BASE_URL}/tasks/match",
            json={"latitude": 6.1319, "longitude": 1.2228, "radius_km": 50},
        )
        assert matched.status_code == 200
        mids = matched.json()
        assert mids["success"] is True
        assert any(row.get("id") == task_id for row in mids["data"])

        ticket_r = await client.post(f"{BASE_URL}/auth/ws-ticket", json={})
        assert ticket_r.status_code == 200
        ticket_js = ticket_r.json()
        assert ticket_js["success"] is True
        ticket = ticket_js["data"]["ticket"]

        uri = f"{WS_ORIGIN}/ws/tasks/{task_id}"

    async def _ws():
        async with websockets.connect(uri, open_timeout=15, close_timeout=5) as ws:
            await ws.send(json.dumps({"type": "auth", "ticket": ticket}))
            await ws.send("e2e-hello")
            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
            return raw

    raw_msg = await _ws()
    body = json.loads(raw_msg)
    assert body.get("message") == "e2e-hello"

    async with httpx.AsyncClient(timeout=45.0, headers=headers) as client:
        deleted = await client.delete(f"{BASE_URL}/tasks/{task_id}")
        assert deleted.status_code == 200
        assert deleted.json()["success"] is True


@pytest.mark.asyncio
async def test_websocket_closes_without_valid_ticket():
    """Connection must not stay open for unauthenticated messaging."""
    tid = str(uuid.uuid4())
    uri = f"{WS_ORIGIN}/ws/tasks/{tid}"
    async with websockets.connect(uri, open_timeout=10) as ws:
        await ws.send(json.dumps({"type": "auth", "ticket": "00000000-0000-0000-0000-000000000000"}))
        with pytest.raises(websockets.exceptions.ConnectionClosed):
            await ws.recv()


@pytest.mark.asyncio
async def test_api_envelope_on_auth_error():
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": "nope@nope.com", "password": "wrongpass"},
        )
        assert r.status_code == 401
        body = r.json()
        assert "success" in body
        assert body["success"] is False
