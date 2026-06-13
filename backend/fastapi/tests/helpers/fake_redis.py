from __future__ import annotations

import threading
import time


class FakeRedisPipeline:
    def __init__(self, redis: "FakeRedis") -> None:
        self._redis = redis
        self._ops: list[tuple[str, tuple, dict]] = []

    def incr(self, key: str):
        self._ops.append(("incr", (key,), {}))
        return self

    def expire(self, key: str, ttl_seconds: int):
        self._ops.append(("expire", (key, ttl_seconds), {}))
        return self

    def execute(self):
        results = []
        with self._redis._lock:
            for op, args, kwargs in self._ops:
                results.append(getattr(self._redis, f"_pipe_{op}")(*args, **kwargs))
        self._ops.clear()
        return results


class FakeRedis:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._expires_at: dict[str, float] = {}
        self._lock = threading.RLock()

    def _purge_if_expired(self, key: str) -> None:
        expires_at = self._expires_at.get(key)
        if expires_at is not None and expires_at <= time.time():
            self._values.pop(key, None)
            self._expires_at.pop(key, None)

    def setex(self, key: str, ttl_seconds: int, value: str) -> bool:
        with self._lock:
            self._values[key] = value
            self._expires_at[key] = time.time() + max(int(ttl_seconds), 0)
            return True

    def get(self, key: str):
        with self._lock:
            self._purge_if_expired(key)
            return self._values.get(key)

    def delete(self, *keys: str) -> int:
        deleted = 0
        with self._lock:
            for key in keys:
                self._purge_if_expired(key)
                if key in self._values:
                    deleted += 1
                self._values.pop(key, None)
                self._expires_at.pop(key, None)
        return deleted

    def getdel(self, key: str):
        with self._lock:
            self._purge_if_expired(key)
            value = self._values.pop(key, None)
            self._expires_at.pop(key, None)
            return value

    def eval(self, _script: str, _numkeys: int, key: str):
        return self.getdel(key)

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        with self._lock:
            self._purge_if_expired(key)
            if nx and key in self._values:
                return None
            self._values[key] = value
            if ex is not None:
                self._expires_at[key] = time.time() + max(int(ex), 0)
            else:
                self._expires_at.pop(key, None)
            return True

    def ttl(self, key: str) -> int:
        with self._lock:
            self._purge_if_expired(key)
            if key not in self._values:
                return -2
            expires_at = self._expires_at.get(key)
            if expires_at is None:
                return -1
            remaining = int(expires_at - time.time())
            return max(remaining, 0)

    def pipeline(self, transaction: bool = False):
        return FakeRedisPipeline(self)

    def publish(self, _channel: str, _payload: str) -> int:
        return 1

    def ping(self) -> bool:
        return True

    def scan(self, cursor: int, match: str | None = None, count: int = 100):
        with self._lock:
            for key in list(self._values.keys()):
                self._purge_if_expired(key)
            keys = sorted(self._values.keys())
            if match and match.endswith("*"):
                prefix = match[:-1]
                keys = [key for key in keys if key.startswith(prefix)]
            return 0, keys[:count]

    def info(self, _section: str | None = None) -> dict[str, int]:
        return {
            "total_commands_processed": 0,
            "connected_clients": 1,
        }

    def _pipe_incr(self, key: str) -> int:
        self._purge_if_expired(key)
        current = int(self._values.get(key, "0"))
        current += 1
        self._values[key] = str(current)
        return current

    def _pipe_expire(self, key: str, ttl_seconds: int) -> bool:
        if key not in self._values:
            return False
        self._expires_at[key] = time.time() + max(int(ttl_seconds), 0)
        return True
