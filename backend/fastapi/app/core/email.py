"""Brevo Transactional Email — HTTP API.

No SMTP relay, no IP allowlist required.
API reference: https://developers.brevo.com/reference/sendtransacemail
"""
from __future__ import annotations

import httpx

from app.core.config import settings
from app.core.observability import logger

_ENDPOINT = "https://api.brevo.com/v3/smtp/email"
_TIMEOUT = 10.0


# ── Internal helpers ──────────────────────────────────────────────────────────

def _headers() -> dict[str, str]:
    return {
        "api-key": settings.brevo_api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }


def _build_payload(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = "",
) -> dict:
    """Build a Brevo-compliant email payload.

    Extend this function to support CC, BCC, reply-to, attachments,
    or template IDs as needed.
    """
    payload: dict = {
        "sender": {
            "name": settings.email_from_name,
            "email": settings.email_from_address,
        },
        "to": [{"email": to_email}],
        "subject": subject,
        "htmlContent": html_content,
    }
    if text_content:
        payload["textContent"] = text_content
    return payload


def _check_config() -> str | None:
    """Return an error message if required settings are missing, else None."""
    if not settings.brevo_api_key.strip():
        return "BREVO_API_KEY is not set"
    if not settings.email_from_address.strip():
        return "EMAIL_FROM_ADDRESS is not set"
    return None


# ── Public API ────────────────────────────────────────────────────────────────

def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: str = "",
) -> bool:
    """Send a transactional email via Brevo HTTP API.

    Returns True only on HTTP 201 (Brevo accepted the message).
    Returns False and logs the reason on any failure.
    Never raises.
    """
    config_error = _check_config()
    if config_error:
        logger.error("send_email: {}", config_error)
        return False

    payload = _build_payload(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content,
    )

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            response = client.post(_ENDPOINT, json=payload, headers=_headers())

        if response.status_code == 201:
            logger.info("Email accepted by Brevo → {} | subject: {}", to_email, subject)
            return True

        logger.error(
            "Brevo rejected email → {} | HTTP {} | body: {}",
            to_email,
            response.status_code,
            response.text[:400],
        )
        return False

    except httpx.TimeoutException:
        logger.error("Brevo API timeout → {}", to_email)
        return False
    except httpx.RequestError as exc:
        logger.error("Brevo API network error → {} | {}", to_email, exc)
        return False


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Send an OTP verification code via Brevo HTTP API."""
    return send_email(
        to_email=to_email,
        subject="Votre code OTP",
        html_content=f"<p>Code : <strong>{otp_code}</strong></p>",
        text_content=f"Code : {otp_code}",
    )
