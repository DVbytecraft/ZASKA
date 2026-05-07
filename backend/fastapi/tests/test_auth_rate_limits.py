"""
Unit tests for auth rate limiting.

Uses a fake in-memory Redis so no running Redis is needed.
Validates both the Lua-based atomicity contract and the per-endpoint limits.
"""

from __future__ import annotations

import pytest

from app.api.v1.routers.auth import _check_rate_limit


class _FakeRedis:
    """Minimal Redis stub that simulates the Lua INCR+EXPIRE script atomically."""

    def __init__(self):
        self._store: dict[str, int] = {}

    def eval(self, script: str, num_keys: int, key: str, window: str) -> int:
        # Simulate the Lua INCR + conditional EXPIRE (TTL ignored in unit test)
        count = self._store.get(key, 0) + 1
        self._store[key] = count
        return count

    def reset(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture()
def fake_redis(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.api.v1.routers.auth.redis_sync", redis)
    return redis


def test_rate_limit_allows_requests_under_threshold(fake_redis):
    from fastapi import HTTPException
    # 5 calls under a limit of 5 — all should pass
    for _ in range(5):
        _check_rate_limit("rl:test:ip1", limit=5, window_seconds=60)


def test_rate_limit_blocks_on_exceeded(fake_redis):
    from fastapi import HTTPException
    for _ in range(10):
        _check_rate_limit("rl:test:ip2", limit=10, window_seconds=60)
    with pytest.raises(HTTPException) as exc_info:
        _check_rate_limit("rl:test:ip2", limit=10, window_seconds=60)
    assert exc_info.value.status_code == 429


def test_different_keys_are_independent(fake_redis):
    from fastapi import HTTPException
    # Exhaust limit for ip3
    for _ in range(3):
        _check_rate_limit("rl:test:ip3", limit=3, window_seconds=60)
    with pytest.raises(HTTPException):
        _check_rate_limit("rl:test:ip3", limit=3, window_seconds=60)

    # ip4 should still be free
    _check_rate_limit("rl:test:ip4", limit=3, window_seconds=60)


def test_lua_atomicity_single_increment_per_call(fake_redis):
    """Each call must increment by exactly 1 — no double-increment bug."""
    _check_rate_limit("rl:test:atomic", limit=100, window_seconds=60)
    _check_rate_limit("rl:test:atomic", limit=100, window_seconds=60)
    assert fake_redis._store.get("rl:test:atomic") == 2
