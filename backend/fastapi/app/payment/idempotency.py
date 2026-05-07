from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from app.core.redis_client import redis_sync


@dataclass(frozen=True)
class IdempotencyResult:
    key: str
    lock_key: str
    fingerprint: str


class IdempotencyError(Exception):
    pass


class IdempotencyService:
    def __init__(self, ttl_seconds: int = 120) -> None:
        self.ttl_seconds = ttl_seconds

    @staticmethod
    def build_key(*parts: str) -> str:
        raw = ":".join(parts)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:40]

    @staticmethod
    def _fingerprint(payload: str) -> str:
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @contextmanager
    def lock(self, idempotency_key: str, payload_fingerprint: str) -> Iterator[IdempotencyResult]:
        lock_key = f"payment:lock:{idempotency_key}"
        request_key = f"payment:req:{idempotency_key}"
        seen = redis_sync.get(request_key)
        if seen and seen != payload_fingerprint:
            raise IdempotencyError("Idempotency key reuse with different payload")

        locked = redis_sync.set(lock_key, "1", nx=True, ex=self.ttl_seconds)
        if not locked:
            raise IdempotencyError("Duplicate in-flight request detected")

        redis_sync.set(request_key, payload_fingerprint, ex=self.ttl_seconds * 10)
        try:
            yield IdempotencyResult(
                key=idempotency_key,
                lock_key=lock_key,
                fingerprint=payload_fingerprint,
            )
        finally:
            redis_sync.delete(lock_key)
