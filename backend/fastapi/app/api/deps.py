from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_engine import CountryEngineService, FeatureFlagEngine, PaymentRouterService
from app.core.redis_client import redis_sync
from app.core.security import decode_token, get_token_version
from app.db.session import get_db
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.chat_service import ChatService
from app.services.feature_flag_service import FeatureFlagService
from app.services.kyc_service import KycService
from app.services.payment_service import PaymentService
from app.services.task_service import TaskService
from app.services.wallet_service import WalletService

_KYC_REJECTED_MSG = (
    "Votre dossier KYC a été refusé. "
    "Veuillez soumettre un nouveau dossier pour accéder aux paiements."
)
_KYC_NOT_APPROVED_MSG = (
    "Votre identité doit être vérifiée avant d'effectuer des paiements. "
    "Soumettez vos documents KYC dans l'onglet Profil."
)
_KYC_EXPIRED_MSG = (
    "Votre vérification KYC a expiré. "
    "Soumettez un nouveau dossier pour continuer à effectuer des paiements."
)

bearer_scheme = HTTPBearer(auto_error=False)


# ── Auth ───────────────────────────────────────────────────────────────────

def get_current_user_id(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> str:
    import logging as _log
    if credentials is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = decode_token(credentials.credentials)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    # Blacklist check (explicit logout / admin revocation) — fail-open if Redis is down
    try:
        if redis_sync.get(f"blacklist:{credentials.credentials}"):
            raise HTTPException(status_code=401, detail="Token revoked")
    except HTTPException:
        raise
    except Exception as _e:
        _log.getLogger(__name__).warning("auth: Redis blacklist check failed (Redis down?) — %s", _e)

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    # Per-user token version check (password reset / forced logout) — fail-open if Redis is down
    # Rationale: Redis downtime is rare and temporary; blocking ALL auth causes more harm
    # than the narrow window of an already-revoked token being accepted briefly.
    token_ver = payload.get("ver")
    if token_ver is None:
        raise HTTPException(status_code=401, detail="Token invalide — reconnectez-vous")
    try:
        current_ver = get_token_version(str(user_id))
        if int(token_ver) < current_ver:
            raise HTTPException(status_code=401, detail="Token revoked — please log in again")
    except HTTPException:
        raise
    except Exception as _e:
        _log.getLogger(__name__).warning(
            "auth: token_version check failed (Redis down?) user=%s — %s. Proceeding fail-open.", user_id, _e
        )

    return str(user_id)


def require_verified_user(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Require email/phone OTP verification before creating or applying to tasks."""
    user = db.get(User, user_id)
    if user is None or not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Compte non vérifié. Validez votre email ou téléphone pour accéder à cette fonctionnalité.",
        )
    return user_id


def require_admin(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Require the authenticated user to have admin role."""
    user = db.get(User, user_id)
    if user is None or user.role != settings.admin_role:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def require_kyc_not_rejected(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Raise 403 if the user's most recent KYC submission was rejected.

    pending / not_submitted → allowed (limited usage).
    rejected → blocked for all write payment operations.
    """
    kyc = KycService(db).get_status(user_id)
    if kyc is not None and kyc.status == "rejected":
        raise HTTPException(status_code=403, detail=_KYC_REJECTED_MSG)
    return user_id


def require_kyc_approved(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Require KYC status == 'approved' and not expired for high-value operations.

    pending / not_submitted / rejected → 403 not-approved.
    approved but expired → 403 expired (must resubmit).
    """
    kyc = KycService(db).get_status(user_id)
    if kyc is None or kyc.status != "approved":
        raise HTTPException(status_code=403, detail=_KYC_NOT_APPROVED_MSG)
    if kyc.is_expired:
        raise HTTPException(status_code=403, detail=_KYC_EXPIRED_MSG)
    return user_id


# ── Country Runtime Engine ─────────────────────────────────────────────────

def get_country_engine() -> CountryEngineService:
    return CountryEngineService(redis_sync)


def get_country_code(
    request: Request,
    cre: CountryEngineService = Depends(get_country_engine),
) -> str:
    return cre.detect_country_from_request(request)


def get_feature_engine(db: Session = Depends(get_db)) -> FeatureFlagEngine:
    return FeatureFlagEngine(redis_sync, db)


def get_payment_router() -> PaymentRouterService:
    return PaymentRouterService()


# ── Services ───────────────────────────────────────────────────────────────

def get_auth_service(db: Session = Depends(get_db)) -> AuthService:
    return AuthService(db)


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_feature_flag_service(db: Session = Depends(get_db)) -> FeatureFlagService:
    return FeatureFlagService(db)


def get_kyc_service(db: Session = Depends(get_db)) -> KycService:
    return KycService(db)


def get_wallet_service(db: Session = Depends(get_db)) -> WalletService:
    return WalletService(db)
