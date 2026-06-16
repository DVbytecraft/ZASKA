from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import MetaData, Table, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.country_engine import CountryEngineService, FeatureFlagEngine, PaymentRouterService
from app.core.redis_client import redis_sync
from app.core.security import decode_token, get_token_version
from app.db.session import get_async_db, get_db
from app.models.user import User
from app.services.access_control_service import AccessControlService
from app.services.aml_service import AmlService
from app.services.accounting_ledger_service import AccountingLedgerService
from app.services.b2b_service import B2BService
from app.services.auth_service import AuthService
from app.services.country_rollout_service import CountryRolloutService
from app.services.chat_service import ChatService
from app.services.dispute_service import DisputeService
from app.services.feature_flag_service import FeatureFlagService
from app.services.food_service import FoodService
from app.services.geo_hierarchy_service import GeoHierarchyService
from app.services.kyc_service import KycService
from app.services.module_control_service import ModuleControlService
from app.services.maps_service import MapsService
from app.services.payment_service import PaymentService
from app.services.referral_service import ReferralService
from app.services.api_key_service import ApiKeyError, ApiKeyService
from app.services.shop_service import ShopService
from app.services.subscription_service import SubscriptionService
from app.services.task_service import TaskService
from app.services.vtc_service import VtcService
from app.services.wallet_service import AsyncWalletService, WalletService

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
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc
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


def require_country_live_access(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    user = db.get(User, user_id)
    if user is None or not user.is_verified:
        raise HTTPException(
            status_code=403,
            detail="Compte non vérifié. Validez votre email ou téléphone pour continuer.",
        )
    if not user.country_code:
        raise HTTPException(
            status_code=403,
            detail="Votre pays n'est pas encore renseigné. Complétez votre profil pour continuer.",
        )
    try:
        CountryRolloutService(db).assert_country_live(user.country_code)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    return user_id


def require_tasker_security_clearance(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if user.role != "tasker":
        raise HTTPException(status_code=403, detail="Réservé aux taskers.")
    if not user.is_verified:
        raise HTTPException(status_code=403, detail="Compte non vérifié.")
    if user.is_suspended or user.is_locked:
        raise HTTPException(status_code=403, detail="Votre compte est temporairement indisponible.")
    if not user.country_code:
        raise HTTPException(status_code=403, detail="Pays du tasker manquant.")
    try:
        CountryRolloutService(db).assert_country_live(user.country_code)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    feature_engine = FeatureFlagEngine(redis_sync, db)
    if not feature_engine.get_flag(user.country_code, "strict_tasker_security"):
        return user_id

    if not user.tasker_security_verified:
        raise HTTPException(
            status_code=403,
            detail="Votre profil tasker n'a pas encore validé tous les protocoles de sécurité Zaska.",
        )
    if not user.biometric_enabled:
        raise HTTPException(
            status_code=403,
            detail="La biométrie doit être activée avant de répondre aux tâches.",
        )
    if user.criminal_record_status not in {"clear", "approved"}:
        raise HTTPException(
            status_code=403,
            detail="Votre casier judiciaire doit être validé avant de répondre aux tâches.",
        )
    kyc = KycService(db).get_status(user_id)
    if kyc is None or kyc.status != "approved" or kyc.is_expired:
        raise HTTPException(
            status_code=403,
            detail="Votre KYC doit être approuvé et valide avant de répondre aux tâches.",
        )
    if getattr(kyc, "biometric_status", "pending") not in {"approved", "clear"}:
        raise HTTPException(
            status_code=403,
            detail="Votre selfie biométrique KYC doit être validé avant de répondre aux tâches.",
        )
    if getattr(kyc, "criminal_record_status", "pending") not in {"clear", "approved"}:
        raise HTTPException(
            status_code=403,
            detail="Le casier judiciaire lié à votre KYC doit être validé.",
        )
    if getattr(kyc, "criminal_record_risk_level", "pending") not in {"low", "clear", "approved"}:
        raise HTTPException(
            status_code=403,
            detail="Le niveau de risque de votre casier judiciaire ne permet pas encore l'accès aux tâches.",
        )
    return user_id


def require_admin(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Require the authenticated user to have admin role and not be suspended/locked."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=403, detail="Admin access required")
    if user.is_suspended or user.is_locked:
        raise HTTPException(status_code=403, detail="Admin access revoked")
    if not AccessControlService(db).is_platform_admin(user_id, user=user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user_id


def require_permission(permission_code: str):
    def _dependency(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> str:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if user.is_suspended or user.is_locked:
            raise HTTPException(status_code=403, detail="Access revoked")
        if not AccessControlService(db).has_permission(user_id, permission_code, user=user):
            raise HTTPException(status_code=403, detail="Permission insuffisante")
        return user_id

    return _dependency


def _load_admin_scope_rows(user_id: str, db: Session) -> list[dict]:
    bind = db.get_bind()
    if bind is None:
        return []
    metadata = MetaData()
    try:
        scopes_table = Table("admin_scopes", metadata, autoload_with=bind)
    except Exception:
        return []

    rows: list[dict] = []
    if "user_id" in scopes_table.c:
        result = db.execute(select(scopes_table).where(scopes_table.c.user_id == user_id)).all()
        rows = [dict(row._mapping) for row in result]
    else:
        try:
            assignments_table = Table("user_role_assignments", metadata, autoload_with=bind)
        except Exception:
            return []
        join_key = None
        for candidate in ("user_role_assignment_id", "assignment_id", "role_assignment_id"):
            if candidate in scopes_table.c:
                join_key = candidate
                break
        if join_key is None or "id" not in assignments_table.c or "user_id" not in assignments_table.c:
            return []
        stmt = (
            select(scopes_table)
            .select_from(scopes_table.join(assignments_table, scopes_table.c[join_key] == assignments_table.c.id))
            .where(assignments_table.c.user_id == user_id)
        )
        result = db.execute(stmt).all()
        rows = [dict(row._mapping) for row in result]
    return rows


def get_admin_scope_context(user_id: str, db: Session) -> dict:
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Unauthorized")
    rows = _load_admin_scope_rows(user_id, db)
    is_unrestricted = user.role == settings.admin_role and len(rows) == 0
    return {"user": user, "scopes": rows, "is_unrestricted": is_unrestricted}


def _scope_allows(
    scopes: list[dict],
    *,
    country_code: str | None,
    continent_code: str | None,
    module_key: str,
    write: bool,
) -> bool:
    normalized_country = country_code.upper() if country_code else None
    normalized_continent = continent_code.upper() if continent_code else None
    target_module = module_key.upper()
    for row in scopes:
        scope_type = str(row.get("scope_type") or "").lower()
        scope_value = str(row.get("scope_value") or "*").upper()
        row_module = str(row.get("module_key") or "*").upper()
        can_read = bool(row.get("can_read", False))
        can_write = bool(row.get("can_write", False))
        if row_module not in {"*", target_module}:
            continue
        if write and not can_write:
            continue
        if not write and not (can_read or can_write):
            continue
        if scope_type in {"global", "all"} or scope_value == "*":
            return True
        if scope_type == "country" and normalized_country and scope_value == normalized_country:
            return True
        if scope_type == "continent" and normalized_continent and scope_value == normalized_continent:
            return True
    return False


def assert_admin_scope_access(
    *,
    user_id: str,
    db: Session,
    module_key: str,
    country_code: str | None = None,
    continent_code: str | None = None,
    write: bool = False,
) -> None:
    context = get_admin_scope_context(user_id, db)
    if context["is_unrestricted"]:
        return
    if not context["scopes"]:
        raise HTTPException(status_code=403, detail="Aucun scope admin actif pour cette opération")
    if not _scope_allows(
        context["scopes"],
        country_code=country_code,
        continent_code=continent_code,
        module_key=module_key,
        write=write,
    ):
        raise HTTPException(status_code=403, detail="Cette opération dépasse votre périmètre pays/continent")


def filter_records_for_admin_scope(
    *,
    records: list[dict],
    user_id: str,
    db: Session,
    module_key: str,
    country_key: str = "countryCode",
    continent_key: str = "continentCode",
) -> list[dict]:
    context = get_admin_scope_context(user_id, db)
    if context["is_unrestricted"]:
        return records
    if not context["scopes"]:
        return []
    return [
        item
        for item in records
        if _scope_allows(
            context["scopes"],
            country_code=item.get(country_key),
            continent_code=item.get(continent_key),
            module_key=module_key,
            write=False,
        )
    ]


def require_module_enabled_for_current_user(module_code: str):
    def _dependency(
        user_id: str = Depends(get_current_user_id),
        db: Session = Depends(get_db),
    ) -> str:
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not user.country_code:
            raise HTTPException(status_code=403, detail="Votre pays n'est pas encore renseigné.")
        try:
            ModuleControlService(db).assert_module_enabled(user.country_code, module_code)
        except ValueError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        return user_id

    return _dependency


def require_kyc_not_rejected(
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
) -> str:
    """Raise 403 if the user's most recent KYC submission was rejected.

    pending / not_submitted → allowed (limited usage).
    rejected → blocked for all write payment operations.
    Demo users (is_demo=True) bypass this check entirely.
    """
    user = db.get(User, user_id)
    if user is not None and user.is_demo:
        return user_id
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
    Demo users (is_demo=True) bypass this check entirely.
    """
    user = db.get(User, user_id)
    if user is not None and user.is_demo:
        return user_id
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


def get_access_control_service(db: Session = Depends(get_db)) -> AccessControlService:
    return AccessControlService(db)


def get_aml_service(db: Session = Depends(get_db)) -> AmlService:
    return AmlService(db)


def get_accounting_ledger_service(db: Session = Depends(get_db)) -> AccountingLedgerService:
    return AccountingLedgerService(db)


def get_b2b_service(db: Session = Depends(get_db)) -> B2BService:
    return B2BService(db)


def get_module_control_service(db: Session = Depends(get_db)) -> ModuleControlService:
    return ModuleControlService(db)


def get_geo_hierarchy_service(db: Session = Depends(get_db)) -> GeoHierarchyService:
    return GeoHierarchyService(db)


def get_maps_service(db: Session = Depends(get_db)) -> MapsService:
    return MapsService(db)


def get_task_service(db: Session = Depends(get_db)) -> TaskService:
    return TaskService(db)


def get_payment_service(db: Session = Depends(get_db)) -> PaymentService:
    return PaymentService(db)


def get_chat_service(db: Session = Depends(get_db)) -> ChatService:
    return ChatService(db)


def get_feature_flag_service(db: Session = Depends(get_db)) -> FeatureFlagService:
    return FeatureFlagService(db)


def get_food_service(db: Session = Depends(get_db)) -> FoodService:
    return FoodService(db)


def get_dispute_service(db: Session = Depends(get_db)) -> DisputeService:
    return DisputeService(db)


def get_kyc_service(db: Session = Depends(get_db)) -> KycService:
    return KycService(db)


def get_wallet_service(db: Session = Depends(get_db)) -> WalletService:
    return WalletService(db)


def get_async_wallet_service(db: AsyncSession = Depends(get_async_db)) -> AsyncWalletService:
    return AsyncWalletService(db)


def get_subscription_service(db: Session = Depends(get_db)) -> SubscriptionService:
    return SubscriptionService(db)


def get_vtc_service(db: Session = Depends(get_db)) -> VtcService:
    return VtcService(db)


def get_referral_service(db: Session = Depends(get_db)) -> ReferralService:
    return ReferralService(db)


def get_shop_service(db: Session = Depends(get_db)) -> ShopService:
    return ShopService(db)


# ── B2B API keys / sandbox ──────────────────────────────────────────────────

class ApiKeyContext:
    """Resolved identity of a request authenticated via an X-API-Key header."""

    def __init__(self, api_key_id: str, organization_id: str, scopes: list[str], is_sandbox: bool):
        self.api_key_id = api_key_id
        self.organization_id = organization_id
        self.scopes = scopes
        self.is_sandbox = is_sandbox


def get_api_key_context(request: Request, db: Session = Depends(get_db)) -> ApiKeyContext:
    raw_key = request.headers.get("X-API-Key")
    if not raw_key:
        raise HTTPException(status_code=401, detail="En-tête X-API-Key requis")

    service = ApiKeyService(db)
    try:
        api_key = service.verify_api_key(raw_key)
    except ApiKeyError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc

    if not service.check_rate_limit(api_key):
        raise HTTPException(status_code=429, detail="Limite de requêtes par minute dépassée")

    return ApiKeyContext(
        api_key_id=api_key.id,
        organization_id=api_key.organization_id,
        scopes=service.get_scopes(api_key),
        is_sandbox=bool(api_key.is_sandbox),
    )


def require_api_key_scope(scope: str):
    def _dependency(ctx: ApiKeyContext = Depends(get_api_key_context)) -> ApiKeyContext:
        if "*" not in ctx.scopes and scope not in ctx.scopes:
            raise HTTPException(status_code=403, detail=f"Scope '{scope}' requis pour cette clé API")
        return ctx

    return _dependency
