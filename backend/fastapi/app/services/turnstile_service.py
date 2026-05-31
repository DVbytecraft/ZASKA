"""Cloudflare Turnstile server-side verification.

Bypass rules:
- TURNSTILE_SECRET_KEY not set → always pass (dev mode)
- Token == 'dev-bypass-token' → pass only in non-production envs
- Cloudflare API error → fail-open in dev/staging, fail-closed in production
"""

import httpx

from app.core.config import settings
from app.core.observability import logger

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"


def verify_turnstile_token(token: str | None, remote_ip: str | None = None) -> bool:
    """Verify a Turnstile token synchronously. Returns True if verification passes."""
    secret = settings.turnstile_secret_key.strip()
    env = str(settings.env).strip().lower()

    if not secret:
        logger.debug("turnstile:bypass secret_not_set")
        return True

    if not token or token == "dev-bypass-token":
        if env != "production":
            logger.debug("turnstile:bypass dev_token env={}", env)
            return True
        logger.warning("turnstile:rejected missing_or_dev_token in production")
        return False

    try:
        data = {"secret": secret, "response": token}
        if remote_ip:
            data["remoteip"] = remote_ip

        with httpx.Client(timeout=5.0) as client:
            resp = client.post(_VERIFY_URL, data=data)
            resp.raise_for_status()
            result = resp.json()
            success = bool(result.get("success", False))

            if not success:
                logger.warning(
                    "turnstile:failed error_codes={}",
                    result.get("error-codes", []),
                )
            return success

    except Exception as exc:
        logger.error("turnstile:error {}", exc)
        # Fail-open in dev/staging to avoid blocking users during Cloudflare outages
        return env != "production"
