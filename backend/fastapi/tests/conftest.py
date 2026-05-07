"""Wait for API before integration tests (avoids races right after container start)."""

from __future__ import annotations

import os
import time

import httpx
import pytest


def _health_url() -> str:
    api = os.getenv("TEST_API_URL", "http://127.0.0.1:6969/api").rstrip("/")
    if api.endswith("/api"):
        return api[: -len("/api")] + "/health"
    return "http://127.0.0.1:6969/health"


@pytest.fixture(scope="session", autouse=True)
def wait_for_live_api():
    url = _health_url()
    last_err: str | None = None
    for _ in range(90):
        try:
            r = httpx.get(url, timeout=2.0)
            if r.status_code == 200:
                body = r.json()
                if body.get("success") is True:
                    return
                last_err = f"unexpected body: {body!r}"
        except Exception as exc:
            last_err = repr(exc)
        time.sleep(1)
    pytest.fail(f"API unhealthy after wait: GET {url} — {last_err}")
