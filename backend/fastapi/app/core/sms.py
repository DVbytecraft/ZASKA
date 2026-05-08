"""SMS dispatch — thin wrapper around the configured SMS provider.

Currently supports Brevo (Sendinblue) Transactional SMS.
Falls back to a no-op log if BREVO_API_KEY is not set.
"""

from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.observability import logger


def send_sms(phone: str, message: str) -> None:
    """Send a transactional SMS. Raises on HTTP error."""
    api_key = getattr(settings, "brevo_api_key", "").strip()
    if not api_key:
        logger.warning("sms:no_api_key phone={} message_preview={}", phone, message[:40])
        return

    resp = httpx.post(
        "https://api.brevo.com/v3/transactionalSMS/sms",
        headers={"api-key": api_key, "Content-Type": "application/json"},
        json={
            "sender": "ZASKA",
            "recipient": phone,
            "content": message,
            "type": "transactional",
        },
        timeout=10,
    )
    resp.raise_for_status()
    logger.info("sms:sent phone={} status={}", phone, resp.status_code)
