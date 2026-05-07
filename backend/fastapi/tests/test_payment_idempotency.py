import pytest

from app.payment.idempotency import IdempotencyError, IdempotencyService


class _FakeRedis:
    def __init__(self):
        self.store: dict[str, str] = {}

    def get(self, key: str):
        return self.store.get(key)

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        _ = ex
        if nx and key in self.store:
            return False
        self.store[key] = value
        return True

    def delete(self, key: str):
        self.store.pop(key, None)


def test_idempotency_lock_blocks_second_inflight(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.payment.idempotency.redis_sync", fake)
    service = IdempotencyService(ttl_seconds=30)

    with service.lock("idem-1", "payload-a"):
        with pytest.raises(IdempotencyError):
            with service.lock("idem-1", "payload-a"):
                pass


def test_idempotency_rejects_different_payload_same_key(monkeypatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.payment.idempotency.redis_sync", fake)
    service = IdempotencyService(ttl_seconds=30)

    with service.lock("idem-1", "payload-a"):
        pass
    with pytest.raises(IdempotencyError):
        with service.lock("idem-1", "payload-b"):
            pass
