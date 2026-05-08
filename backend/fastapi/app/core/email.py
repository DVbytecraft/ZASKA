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


def _otp_html(title: str, intro: str, otp_code: str, expire_minutes: int) -> str:
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <!-- Header -->
        <tr>
          <td style="background:#6D28D9;padding:28px 32px;text-align:center;">
            <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:1px;">ZASKA</span>
          </td>
        </tr>
        <!-- Body -->
        <tr>
          <td style="padding:36px 32px 24px;">
            <h2 style="margin:0 0 12px;font-size:20px;color:#111827;">{title}</h2>
            <p style="margin:0 0 28px;font-size:15px;color:#6B7280;line-height:1.6;">{intro}</p>
            <!-- OTP box -->
            <div style="background:#F5F3FF;border:2px dashed #6D28D9;border-radius:12px;padding:24px;text-align:center;margin-bottom:28px;">
              <span style="font-size:36px;font-weight:800;letter-spacing:10px;color:#6D28D9;">{otp_code}</span>
            </div>
            <p style="margin:0;font-size:13px;color:#9CA3AF;text-align:center;">
              Ce code expire dans <strong>{expire_minutes} minutes</strong>.<br>
              Si vous n'avez pas effectué cette demande, ignorez cet email.
            </p>
          </td>
        </tr>
        <!-- Footer -->
        <tr>
          <td style="background:#F9FAFB;padding:16px 32px;text-align:center;border-top:1px solid #E5E7EB;">
            <p style="margin:0;font-size:12px;color:#9CA3AF;">© 2026 ZASKA · Ne pas répondre à cet email</p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_otp_email(to_email: str, otp_code: str) -> bool:
    """Send an account verification OTP via Brevo."""
    from app.core.config import settings as _s
    expire = _s.otp_expire_minutes
    return send_email(
        to_email=to_email,
        subject="Votre code de vérification ZASKA",
        html_content=_otp_html(
            title="Vérifiez votre compte",
            intro="Utilisez le code ci-dessous pour vérifier votre compte ZASKA.",
            otp_code=otp_code,
            expire_minutes=expire,
        ),
        text_content=f"Votre code de vérification ZASKA : {otp_code}\nValide {expire} minutes.",
    )


def send_password_reset_email(to_email: str, otp_code: str) -> bool:
    """Send a password reset OTP via Brevo."""
    from app.core.config import settings as _s
    expire = _s.otp_expire_minutes
    return send_email(
        to_email=to_email,
        subject="Réinitialisation de votre mot de passe ZASKA",
        html_content=_otp_html(
            title="Réinitialisez votre mot de passe",
            intro="Vous avez demandé à réinitialiser votre mot de passe. Utilisez le code ci-dessous.",
            otp_code=otp_code,
            expire_minutes=expire,
        ),
        text_content=f"Code de réinitialisation ZASKA : {otp_code}\nValide {expire} minutes.",
    )
