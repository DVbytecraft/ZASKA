from __future__ import annotations

import json
import secrets
import time
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.redis_client import redis_sync
from app.core.security import get_password_hash, verify_password
from app.models.b2b import ApiKey, BusinessOrganization

_KEY_PREFIX_LEN = 12


class ApiKeyError(ValueError):
    pass


class ApiKeyService:
    """Manage B2B API keys: issuance, verification, scopes, rate limiting, revocation."""

    def __init__(self, db: Session):
        self.db = db

    # ─── Key generation ─────────────────────────────────────────────────────

    @staticmethod
    def _generate_raw_key(*, is_sandbox: bool) -> tuple[str, str]:
        """Return (raw_key, key_prefix). Prefix is stored in clear for fast lookup."""
        env_tag = "test" if is_sandbox else "live"
        token = secrets.token_urlsafe(32)
        raw_key = f"zsk_{env_tag}_{token}"
        key_prefix = raw_key[:_KEY_PREFIX_LEN]
        return raw_key, key_prefix

    # ─── CRUD ────────────────────────────────────────────────────────────────

    def create_api_key(
        self,
        *,
        organization_id: str,
        name: str,
        scopes: list[str],
        is_sandbox: bool = False,
        rate_limit_per_minute: int = 60,
        expires_at: datetime | None = None,
        created_by_user_id: str | None = None,
    ) -> dict:
        if self.db.get(BusinessOrganization, organization_id) is None:
            raise ApiKeyError("Organisation introuvable")

        raw_key, key_prefix = self._generate_raw_key(is_sandbox=is_sandbox)

        api_key = ApiKey(
            organization_id=organization_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=get_password_hash(raw_key),
            scopes_json=json.dumps(scopes),
            is_sandbox=is_sandbox,
            rate_limit_per_minute=rate_limit_per_minute,
            status="active",
            expires_at=expires_at,
            created_by_user_id=created_by_user_id,
        )
        self.db.add(api_key)
        self.db.commit()
        self.db.refresh(api_key)

        result = self._serialize(api_key)
        # The raw key is returned exactly once — it cannot be retrieved again afterwards.
        result["apiKey"] = raw_key
        return result

    def list_api_keys(self, organization_id: str) -> list[dict]:
        rows = self.db.execute(
            select(ApiKey).where(ApiKey.organization_id == organization_id)
        ).scalars().all()
        return [self._serialize(row) for row in rows]

    def revoke_api_key(self, api_key_id: str, organization_id: str) -> dict:
        api_key = self.db.get(ApiKey, api_key_id)
        if api_key is None or api_key.organization_id != organization_id:
            raise ApiKeyError("Clé API introuvable")
        if api_key.status != "revoked":
            api_key.status = "revoked"
            api_key.revoked_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(api_key)
        return self._serialize(api_key)

    # ─── Verification ────────────────────────────────────────────────────────

    def verify_api_key(self, raw_key: str) -> ApiKey:
        """Return the matching active, non-expired ApiKey, or raise ApiKeyError."""
        if not raw_key or len(raw_key) < _KEY_PREFIX_LEN:
            raise ApiKeyError("Clé API invalide")

        key_prefix = raw_key[:_KEY_PREFIX_LEN]
        api_key = self.db.execute(
            select(ApiKey).where(ApiKey.key_prefix == key_prefix)
        ).scalars().one_or_none()
        if api_key is None or not verify_password(raw_key, api_key.key_hash):
            raise ApiKeyError("Clé API invalide")

        if api_key.status != "active":
            raise ApiKeyError("Clé API révoquée")

        if api_key.expires_at is not None:
            expires_at = api_key.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < datetime.now(timezone.utc):
                raise ApiKeyError("Clé API expirée")

        api_key.last_used_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(api_key)
        return api_key

    # ─── Scopes & rate limiting ─────────────────────────────────────────────

    @staticmethod
    def get_scopes(api_key: ApiKey) -> list[str]:
        try:
            scopes = json.loads(api_key.scopes_json)
            return scopes if isinstance(scopes, list) else []
        except Exception:
            return []

    @classmethod
    def check_scope(cls, api_key: ApiKey, required_scope: str) -> bool:
        scopes = cls.get_scopes(api_key)
        return "*" in scopes or required_scope in scopes

    @staticmethod
    def check_rate_limit(api_key: ApiKey) -> bool:
        """Sliding-minute counter via Redis. Returns True if the request is allowed."""
        bucket = int(time.time() // 60)
        key = f"apikey_rate:{api_key.id}:{bucket}"
        pipe = redis_sync.pipeline(transaction=False)
        pipe.incr(key)
        pipe.expire(key, 120)
        count, _ = pipe.execute()
        return int(count) <= api_key.rate_limit_per_minute

    # ─── Serialization ───────────────────────────────────────────────────────

    def _serialize(self, row: ApiKey) -> dict:
        return {
            "id": row.id,
            "organizationId": row.organization_id,
            "name": row.name,
            "keyPrefix": row.key_prefix,
            "scopes": self.get_scopes(row),
            "isSandbox": bool(row.is_sandbox),
            "rateLimitPerMinute": row.rate_limit_per_minute,
            "status": row.status,
            "expiresAt": row.expires_at.isoformat() if row.expires_at else None,
            "lastUsedAt": row.last_used_at.isoformat() if row.last_used_at else None,
            "revokedAt": row.revoked_at.isoformat() if row.revoked_at else None,
            "createdAt": row.created_at.isoformat() if row.created_at else None,
        }
