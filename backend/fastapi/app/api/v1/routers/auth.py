from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_auth_service, get_country_code, get_current_user_id, get_wallet_service
from app.core.country_engine import CountryEngineService, PaymentRouterService
from app.core.redis_client import redis_sync
from app.core.responses import success_response
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import ForgotPasswordPayload, LoginPayload, LogoutPayload, RefreshPayload, RegisterPayload, ResendOtpPayload, ResetPasswordPayload, SetPasswordPayload, VerifyOtpPayload
from app.services.auth_service import AuthService
from app.services.wallet_service import WalletService

router = APIRouter(prefix="/auth", tags=["auth"])

# Lua script: atomic INCR + conditional EXPIRE in a single Redis round-trip.
# Eliminates the TOCTOU race where a crash between INCR and EXPIRE leaves the
# key without a TTL (permanent lock).
_LUA_RATE_LIMIT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
    redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return count
"""


def _check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    count = redis_sync.eval(_LUA_RATE_LIMIT, 1, key, str(window_seconds))
    if count > limit:
        raise HTTPException(
            status_code=429,
            detail="Trop de tentatives — réessayez dans quelques minutes",
        )


def _check_login_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"rl:login:{ip}", limit=10, window_seconds=60)


def _check_otp_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    _check_rate_limit(f"rl:otp:{ip}", limit=5, window_seconds=300)


def _check_register_rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    # Max 5 registrations per IP per hour — prevent mass account creation
    _check_rate_limit(f"rl:register:{ip}", limit=5, window_seconds=3600)


def _check_verify_otp_rate_limit(phone: str) -> None:
    # Max 10 OTP attempts per phone per 10 minutes — prevent brute-force
    _check_rate_limit(f"rl:verify_otp:{phone}", limit=10, window_seconds=600)


@router.post("/register")
def register(
    request: Request,
    payload: RegisterPayload,
    service: AuthService = Depends(get_auth_service),
    wallet_svc: WalletService = Depends(get_wallet_service),
    country_code: str = Depends(get_country_code),
):
    _check_register_rate_limit(request)
    try:
        data = service.register(
            phone=payload.phone,
            password=payload.password,
            first_name=payload.firstName,
            last_name=payload.lastName,
            email=payload.email,
            role=payload.role,
            country_code=payload.country or country_code,
        )
        wallet_svc.create_wallet(user_id=data["userId"], currency="USD")
        wallet_svc.create_wallet(user_id=data["userId"], currency="XOF")
        return success_response(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Registration failed") from exc


@router.post("/set-password")
def set_password(payload: SetPasswordPayload, service: AuthService = Depends(get_auth_service)):
    try:
        service.set_password(email=payload.email.lower(), password=payload.password)
        return success_response({"passwordSet": True})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Set password failed") from exc


@router.post("/verify-otp")
def verify_otp(payload: VerifyOtpPayload, service: AuthService = Depends(get_auth_service)):
    _check_verify_otp_rate_limit(payload.phone)
    try:
        data = service.verify_otp(phone=payload.phone, code=payload.code)
        return success_response(data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="OTP verification failed") from exc


@router.post("/resend-otp")
def resend_otp(
    request: Request,
    payload: ResendOtpPayload,
    service: AuthService = Depends(get_auth_service),
):
    """Resend OTP code to the user's phone/email."""
    _check_otp_rate_limit(request)
    try:
        service.resend_otp(phone=payload.phone)
        return success_response({"sent": True})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Resend failed") from exc


@router.post("/login")
def login(
    payload: LoginPayload,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    country_code: str = Depends(get_country_code),
):
    try:
        _check_login_rate_limit(request)
        data = service.login(email=payload.email, password=payload.password, country_code=country_code)

        cre = CountryEngineService(redis_sync)
        config = cre.get_country_config(country_code)
        route = PaymentRouterService.route_payment(country_code, 0, config.currency)
        data["country"] = country_code
        data["currency"] = config.currency
        data["paymentProvider"] = route.provider
        data["mobileMoneyEnabled"] = config.mobile_money_enabled

        return success_response(data)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Login failed") from exc


@router.post("/refresh")
def refresh(payload: RefreshPayload, service: AuthService = Depends(get_auth_service)):
    try:
        if redis_sync.get(f"blacklist:{payload.refresh_token}"):
            raise HTTPException(status_code=401, detail="Refresh token revoked")
        token_payload = decode_token(payload.refresh_token)
        if token_payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        user_id = token_payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid refresh token")
        return success_response(service.refresh(str(user_id), previous_refresh_token=payload.refresh_token))
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Refresh failed") from exc


@router.post("/ws-ticket")
def ws_ticket(
    task_id: str | None = None,
    service: AuthService = Depends(get_auth_service),
    user_id: str = Depends(get_current_user_id),
):
    """Issue a one-time WebSocket ticket bound to task_id (when provided)."""
    ticket = service.issue_ws_ticket(user_id, task_id=task_id)
    return success_response({"ticket": ticket})


@router.post("/forgot-password")
def forgot_password(
    request: Request,
    payload: ForgotPasswordPayload,
    service: AuthService = Depends(get_auth_service),
):
    """Send password-reset OTP. Always returns success to prevent email enumeration."""
    _check_otp_rate_limit(request)
    try:
        service.forgot_password(email=payload.email)
        return success_response({"sent": True})
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Envoi échoué") from exc


@router.post("/reset-password")
def reset_password(
    request: Request,
    payload: ResetPasswordPayload,
    service: AuthService = Depends(get_auth_service),
):
    _check_otp_rate_limit(request)
    try:
        service.reset_password(email=payload.email, code=payload.code, new_password=payload.new_password)
        return success_response({"reset": True})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Reset failed") from exc


@router.post("/logout")
def logout(payload: LogoutPayload, service: AuthService = Depends(get_auth_service)):
    try:
        service.logout(payload.refresh_token)
        return success_response({"loggedOut": True})
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Logout failed") from exc


class FcmTokenPayload(BaseModel):
    token: str


@router.post("/fcm-token")
def register_fcm_token(
    payload: FcmTokenPayload,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """Register or update the FCM device token for the authenticated user."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Utilisateur introuvable")
    user.fcm_token = payload.token.strip() or None
    db.commit()
    return success_response({"registered": True})
