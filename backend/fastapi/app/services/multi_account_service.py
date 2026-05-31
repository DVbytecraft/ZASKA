"""Multi-account detection via device fingerprinting and IP analysis.

Design:
  - Client sends X-Device-ID header (persistent UUID generated on first install)
  - Backend stores device_id → {user_ids} and ip → {user_ids} in Redis Sets
  - Alert threshold: 3+ distinct users on same device = multi-account suspected

Redis key schema:
  device:<device_id>          Set of user_ids seen on this device   TTL 90d
  ip_users:<ip>               Set of user_ids seen from this IP     TTL 30d
  device_first_seen:<device_id>:<user_id>  Timestamp               TTL 90d
"""

from __future__ import annotations

from app.core.observability import logger

_DEVICE_KEY_PREFIX = "device"
_IP_KEY_PREFIX = "ip_users"
_FIRST_SEEN_PREFIX = "device_first_seen"
_MULTI_ACCOUNT_THRESHOLD = 3  # flag when 1 device → N distinct users


class MultiAccountService:
    @property
    def _redis(self):
        from app.core.redis_client import redis_sync
        return redis_sync

    def register_device(self, user_id: str, device_id: str, ip: str | None = None) -> dict:
        """Record user_id → device_id and optionally ip association.

        Returns risk assessment for this registration event.
        """
        if not device_id or not user_id:
            return {"risk_flag": False, "device_user_count": 0}

        device_key = f"{_DEVICE_KEY_PREFIX}:{device_id}"
        user_devices_key = f"user_devices:{user_id}"
        try:
            self._redis.sadd(device_key, user_id)
            self._redis.expire(device_key, 86400 * 90)

            # Reverse index: user → devices (for TrustService device_trust query)
            self._redis.sadd(user_devices_key, device_id)
            self._redis.expire(user_devices_key, 86400 * 90)

            first_seen_key = f"{_FIRST_SEEN_PREFIX}:{device_id}:{user_id}"
            if not self._redis.exists(first_seen_key):
                import time
                self._redis.setex(first_seen_key, 86400 * 90, str(int(time.time())))

            if ip:
                ip_key = f"{_IP_KEY_PREFIX}:{ip}"
                self._redis.sadd(ip_key, user_id)
                self._redis.expire(ip_key, 86400 * 30)

            device_user_count = self._redis.scard(device_key) or 0
            risk_flag = device_user_count >= _MULTI_ACCOUNT_THRESHOLD

            if risk_flag:
                logger.warning(
                    "multi_account:threshold_exceeded device_id={} user_count={}",
                    device_id,
                    device_user_count,
                )

            return {
                "device_id": device_id,
                "device_user_count": int(device_user_count),
                "risk_flag": risk_flag,
            }
        except Exception as exc:
            logger.error("multi_account:register_device_error error={}", exc)
            return {"risk_flag": False, "device_user_count": 0}

    def get_device_user_count(self, device_id: str) -> int:
        """Return number of distinct users seen on this device."""
        if not device_id:
            return 0
        try:
            return int(self._redis.scard(f"{_DEVICE_KEY_PREFIX}:{device_id}") or 0)
        except Exception:
            return 0

    def get_ip_user_count(self, ip: str) -> int:
        """Return number of distinct users seen from this IP."""
        if not ip:
            return 0
        try:
            return int(self._redis.scard(f"{_IP_KEY_PREFIX}:{ip}") or 0)
        except Exception:
            return 0

    def is_multi_account_suspected(self, device_id: str) -> bool:
        """True if 3+ different users have authenticated from this device."""
        return self.get_device_user_count(device_id) >= _MULTI_ACCOUNT_THRESHOLD

    def get_device_trust_score(self, user_id: str, device_id: str) -> float:
        """0–5 score: single-user device = 5 pts, multi-account = 0, unknown = 0."""
        if not device_id or not user_id:
            return 0.0
        try:
            device_key = f"{_DEVICE_KEY_PREFIX}:{device_id}"
            raw_members = self._redis.smembers(device_key)
            if not raw_members:
                return 0.0
            members = {m.decode() if isinstance(m, bytes) else m for m in raw_members}
            count = len(members)
            if count == 0:
                return 0.0
            if count == 1 and user_id in members:
                return 5.0
            if count >= _MULTI_ACCOUNT_THRESHOLD:
                return 0.0
            return 2.5
        except Exception:
            return 0.0

    def get_users_on_device(self, device_id: str) -> list[str]:
        """Return list of user_ids seen on this device."""
        if not device_id:
            return []
        try:
            raw = self._redis.smembers(f"{_DEVICE_KEY_PREFIX}:{device_id}")
            return [m.decode() if isinstance(m, bytes) else m for m in raw]
        except Exception:
            return []
