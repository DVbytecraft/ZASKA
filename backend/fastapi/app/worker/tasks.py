import logging

from app.core.config import settings
from app.core.redis_client import redis_sync
from app.db.session import SessionLocal
from app.services.email_service import EmailService
from app.services.wallet_service import WalletService
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)
email_service = EmailService()


@celery_app.task(name="app.worker.tasks.cleanup_otp_keys")
def cleanup_otp_keys():
    keys = redis_sync.keys("otp:*")
    return {"active_otp_keys": len(keys)}


@celery_app.task(name="app.worker.tasks.send_otp_notification", bind=True, max_retries=3)
def send_otp_notification(self, email: str, otp_code: str) -> dict:
    try:
        provider = str(settings.otp_provider).strip().lower()
        env_norm = str(settings.env).strip().lower()

        if provider == "mock":
            if env_norm != "development":
                raise RuntimeError("OTP mock provider is forbidden outside development")
            logger.info("[OTP MOCK] Code for %s: %s", email, otp_code)
            return {"delivered": True, "channel": "mock-log", "email": email}

        if provider == "smtp":
            delivered = email_service.send_otp_email(to_email=email, otp_code=otp_code)
            if not delivered:
                raise RuntimeError("SMTP delivery failed")
            return {"delivered": True, "channel": "smtp", "email": email}

        raise RuntimeError(f"Unsupported OTP provider '{provider}'")
    except Exception as exc:
        logger.error("Echec livraison OTP pour %s : %s", email, exc)
        raise self.retry(exc=exc, countdown=30) from exc


@celery_app.task(name="app.worker.tasks.release_escrow_async", bind=True, max_retries=3)
def release_escrow_async(self, escrow_id: str) -> dict:
    db = SessionLocal()
    try:
        svc = WalletService(db)
        escrow = svc.release_escrow_safe(escrow_id)
        svc.finalize_transaction(escrow.id)
        return {"escrow_id": escrow.id, "status": escrow.status}
    except Exception as exc:
        logger.error("Echec release escrow %s : %s", escrow_id, exc)
        raise self.retry(exc=exc, countdown=30) from exc
    finally:
        db.close()
