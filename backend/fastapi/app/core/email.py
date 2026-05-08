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


def _notification_html(icon: str, title: str, body_html: str, cta_text: str = "", cta_url: str = "") -> str:
    cta_block = ""
    if cta_text and cta_url:
        cta_block = (
            f'<div style="text-align:center;margin:24px 0;">'
            f'<a href="{cta_url}" style="background:#6D28D9;color:#ffffff;text-decoration:none;'
            f'padding:14px 32px;border-radius:10px;font-weight:700;font-size:15px;display:inline-block;">'
            f'{cta_text}</a></div>'
        )
    return f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
    <tr><td align="center">
      <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:#6D28D9;padding:28px 32px;text-align:center;">
            <span style="color:#ffffff;font-size:22px;font-weight:700;letter-spacing:1px;">ZASKA</span>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 32px 24px;">
            <div style="font-size:36px;text-align:center;margin-bottom:12px;">{icon}</div>
            <h2 style="margin:0 0 20px;font-size:20px;color:#111827;text-align:center;">{title}</h2>
            {body_html}
            {cta_block}
          </td>
        </tr>
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


def send_task_application_email(
    to_email: str,
    task_title: str,
    tasker_name: str,
    proposed_price: float | None,
    currency: str,
) -> bool:
    from app.core.config import settings as _s
    price_line = (
        f'<p style="margin:8px 0 0;font-size:14px;color:#6B7280;">Prix proposé : '
        f'<strong style="color:#6D28D9;">{proposed_price:,.0f} {currency}</strong></p>'
    ) if proposed_price is not None else ""
    body = (
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.6;">'
        f'<strong>{tasker_name}</strong> a postulé à votre tâche.</p>'
        f'<div style="background:#F5F3FF;border-left:4px solid #6D28D9;border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
        f'<p style="margin:0 0 4px;font-size:16px;font-weight:700;color:#111827;">{task_title}</p>'
        f'{price_line}</div>'
        f'<p style="margin:0;font-size:14px;color:#6B7280;">Connectez-vous pour voir le profil du candidat et accepter ou refuser.</p>'
    )
    return send_email(
        to_email=to_email,
        subject="ZASKA — Nouvelle candidature sur votre tâche",
        html_content=_notification_html("🙋", "Nouvelle candidature reçue", body, "Voir la candidature", _s.app_frontend_url),
        text_content=f"{tasker_name} a postulé à votre tâche : {task_title}",
    )


def send_price_proposal_email(
    to_email: str,
    task_title: str,
    tasker_name: str,
    proposed_price: float,
    currency: str,
) -> bool:
    from app.core.config import settings as _s
    body = (
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.6;">'
        f'<strong>{tasker_name}</strong> demande une modification de prix pour votre tâche.</p>'
        f'<div style="background:#FFF7ED;border-left:4px solid #F59E0B;border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
        f'<p style="margin:0 0 8px;font-size:15px;font-weight:700;color:#111827;">{task_title}</p>'
        f'<p style="margin:0;font-size:20px;font-weight:800;color:#D97706;">{proposed_price:,.0f} {currency}</p>'
        f'</div>'
        f'<p style="margin:0;font-size:14px;color:#6B7280;">Connectez-vous pour accepter ou refuser cette proposition.</p>'
    )
    return send_email(
        to_email=to_email,
        subject="ZASKA — Demande de modification de prix",
        html_content=_notification_html("💰", "Modification de prix demandée", body, "Répondre", _s.app_frontend_url),
        text_content=f"{tasker_name} propose {proposed_price:,.0f} {currency} pour : {task_title}",
    )


def send_message_notification_email(
    to_email: str,
    task_title: str,
    sender_name: str,
    message_preview: str,
) -> bool:
    from app.core.config import settings as _s
    preview = message_preview[:120] + ("…" if len(message_preview) > 120 else "")
    body = (
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.6;">'
        f'<strong>{sender_name}</strong> vous a envoyé un message.</p>'
        f'<div style="background:#F0FDF4;border-left:4px solid #22C55E;border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
        f'<p style="margin:0 0 6px;font-size:12px;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:0.5px;">{task_title}</p>'
        f'<p style="margin:0;font-size:15px;color:#111827;font-style:italic;">&ldquo;{preview}&rdquo;</p>'
        f'</div>'
        f'<p style="margin:0;font-size:14px;color:#6B7280;">Connectez-vous pour répondre.</p>'
    )
    return send_email(
        to_email=to_email,
        subject=f"ZASKA — Nouveau message de {sender_name}",
        html_content=_notification_html("💬", f"Message de {sender_name}", body, "Répondre", _s.app_frontend_url),
        text_content=f"{sender_name} : {preview}",
    )


def send_task_done_email(
    to_email: str,
    task_title: str,
    executor_name: str,
) -> bool:
    from app.core.config import settings as _s
    body = (
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.6;">'
        f'<strong>{executor_name}</strong> a déclaré votre tâche terminée et attend votre confirmation.</p>'
        f'<div style="background:#F0FDF4;border-left:4px solid #22C55E;border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
        f'<p style="margin:0 0 4px;font-size:16px;font-weight:700;color:#111827;">{task_title}</p>'
        f'<p style="margin:0;font-size:13px;color:#6B7280;">Le paiement sera libéré automatiquement dans 24h si vous ne répondez pas.</p>'
        f'</div>'
        f'<p style="margin:0;font-size:14px;color:#6B7280;">Ouvrez l\'application pour <strong>confirmer</strong> ou <strong>contester</strong> la réalisation.</p>'
    )
    return send_email(
        to_email=to_email,
        subject=f"ZASKA — {executor_name} a terminé votre tâche",
        html_content=_notification_html("✅", "Prestation déclarée terminée", body, "Confirmer dans l'app", _s.app_frontend_url),
        text_content=f"{executor_name} a déclaré la tâche '{task_title}' terminée. Confirmez dans l'app dans les 24h.",
    )


def send_kyc_review_email(
    admin_email: str,
    user_display_name: str,
    user_email: str | None,
    user_id: str,
) -> bool:
    from app.core.config import settings as _s
    user_info = user_display_name + (f" ({user_email})" if user_email else "")
    body = (
        f'<p style="margin:0 0 16px;font-size:15px;color:#374151;line-height:1.6;">'
        f'Un nouvel utilisateur attend la validation de son identité.</p>'
        f'<div style="background:#EFF6FF;border-left:4px solid #3B82F6;border-radius:8px;padding:16px 20px;margin-bottom:16px;">'
        f'<p style="margin:0 0 4px;font-size:16px;font-weight:700;color:#111827;">{user_info}</p>'
        f'<p style="margin:0;font-size:13px;color:#6B7280;">ID : {user_id}</p>'
        f'</div>'
        f'<p style="margin:0;font-size:14px;color:#6B7280;">Connectez-vous au dashboard admin pour examiner les documents.</p>'
    )
    return send_email(
        to_email=admin_email,
        subject="ZASKA Admin — Vérification d'identité à examiner",
        html_content=_notification_html("🪪", "KYC en attente de validation", body, "Ouvrir l'admin", _s.app_frontend_url),
        text_content=f"Nouveau KYC à examiner : {user_info} | ID : {user_id}",
    )


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
