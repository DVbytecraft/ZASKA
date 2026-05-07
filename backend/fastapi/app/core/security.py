from datetime import datetime, timedelta, timezone
from typing import Any
import uuid

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

_TOKEN_VERSION_TTL = 86400 * 30  # 30 days — must exceed max token lifetime


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def get_token_version(user_id: str) -> int:
    """Return the current token generation counter for a user (defaults to 0)."""
    from app.core.redis_client import redis_sync

    raw = redis_sync.get(f"token_version:{user_id}")
    return int(raw) if raw else 0


def revoke_all_user_tokens(user_id: str) -> None:
    """Invalidate all existing tokens for a user by incrementing the version counter.

    Any JWT carrying an older 'ver' claim will be rejected by get_current_user_id.
    """
    from app.core.redis_client import redis_sync

    key = f"token_version:{user_id}"
    redis_sync.incr(key)
    redis_sync.expire(key, _TOKEN_VERSION_TTL)


def create_token(subject: str, expires_delta: timedelta, token_type: str) -> str:
    expire = datetime.now(timezone.utc) + expires_delta
    payload: dict[str, Any] = {
        "sub": subject,
        "exp": expire,
        "type": token_type,
        "jti": str(uuid.uuid4()),
        "ver": get_token_version(subject),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
