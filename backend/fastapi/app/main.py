import asyncio
import json

import sentry_sdk
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.api import api_router
from app.api.websocket import (
    call_signaling_loop,
    call_signaling_manager,
    chat_ws_manager,
    user_call_notification_loop,
    user_call_notification_manager,
    websocket_loop,
)
from app.core.config import settings
from app.core.observability import RequestIDMiddleware, logger
from app.core.rate_limit import RedisRateLimitMiddleware
from app.core.responses import error_response, success_response
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.ws_ticket import consume_ws_ticket
from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    audit_log,
    call_session,
    chat_message,
    dispute,
    feature_flag,
    kyc,
    location_config,
    negotiation_event,
    notification,
    payment_method,
    payout,
    support_ticket,
    task,
    task_application,
    task_completion_code,
    user,
    user_address,
    virtual_card,
    wallet,
    webhook_idempotency,
)


app = FastAPI(title=settings.app_name)


def _validate_production_hard_lock() -> None:
    mode = str(settings.payment_mode).strip().lower()
    if mode != "production":
        return
    provider_ok = any(
        [
            bool(settings.stripe_secret_key.strip()),
            bool(settings.fedapay_api_key.strip()),
            bool(settings.flutterwave_secret_key.strip()),
        ]
    )
    if not provider_ok:
        raise RuntimeError("Production hard-lock: at least one payment provider key is required")
    if not any([settings.stripe_webhook_secret, settings.fedapay_webhook_secret, settings.flutterwave_hash]):
        raise RuntimeError("Production hard-lock: webhook secret/hash required")
    if not settings.kyc_provider_enabled:
        raise RuntimeError("Production hard-lock: KYC provider must be enabled")
    if not settings.otp_provider_enabled:
        raise RuntimeError("Production hard-lock: OTP provider must be enabled")


app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Country-Code", "X-Request-ID", "X-Idempotency-Key"],
)
app.add_middleware(
    RedisRateLimitMiddleware,
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)


@app.middleware("http")
async def security_headers_middleware(request, call_next):
    response = await call_next(request)
    env_norm = str(settings.env).strip().lower()
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
    # HSTS only on production (requires HTTPS)
    if env_norm == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    # Remove server fingerprint
    if "server" in response.headers:
        del response.headers["server"]
    return response


@app.on_event("startup")
async def startup() -> None:
    logger.info("ZASKA CORE OS startup env={} version=core-os-1.0", settings.env)
    if settings.sentry_dsn.strip():
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.env)
    _validate_production_hard_lock()
    await chat_ws_manager.start()
    start_scheduler()


@app.on_event("shutdown")
async def shutdown() -> None:
    stop_scheduler()


@app.get("/health")
def health():
    return success_response({"status": "ok"})


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return success_response({"status": "ok"})


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(_, exc: StarletteHTTPException):
    return JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail)))


@app.exception_handler(HTTPException)
async def http_exception_handler(_, exc: HTTPException):
    return JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail)))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError):
    return JSONResponse(status_code=422, content=error_response("Invalid request payload", exc.errors()))


@app.exception_handler(Exception)
async def generic_exception_handler(_, exc: Exception):
    logger.exception("Unhandled exception: {}", exc)
    return JSONResponse(status_code=500, content=error_response("Internal server error"))


@app.websocket("/ws/tasks/{task_id}")
async def websocket_task_chat(websocket: WebSocket, task_id: str) -> None:
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        data = json.loads(raw)
        if data.get("type") != "auth" or not data.get("ticket"):
            await websocket.close(code=1008, reason="Unauthorized")
            return
        user_id = consume_ws_ticket(str(data["ticket"]), expected_task_id=task_id)
        if not user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        await websocket_loop(task_id=task_id, websocket=websocket, user_id=user_id)
    except (TimeoutError, asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(code=1008, reason="Unauthorized")
    except Exception:
        await websocket.close(code=1011, reason="Server error")


@app.websocket("/ws/calls/{call_id}")
async def websocket_call_signaling(websocket: WebSocket, call_id: str) -> None:
    """WebRTC signaling relay: forwards offer/answer/ice/hangup between call participants."""
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        data = json.loads(raw)
        if data.get("type") != "auth" or not data.get("ticket"):
            await websocket.close(code=1008, reason="Unauthorized")
            return
        user_id = consume_ws_ticket(str(data["ticket"]), expected_task_id=call_id)
        if not user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        accepted = await call_signaling_manager.connect(call_id, websocket)
        if not accepted:
            await websocket.close(code=1008, reason="Call room full")
            return
        await call_signaling_loop(call_id=call_id, websocket=websocket)
    except (TimeoutError, asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(code=1008, reason="Unauthorized")
    except Exception:
        call_signaling_manager.disconnect(call_id, websocket)
        await websocket.close(code=1011, reason="Server error")


@app.websocket("/ws/users/{user_id}/calls")
async def websocket_user_call_notifications(websocket: WebSocket, user_id: str) -> None:
    """Push channel for incoming call events to a specific user."""
    await websocket.accept()
    try:
        raw = await asyncio.wait_for(websocket.receive_text(), timeout=15.0)
        data = json.loads(raw)
        if data.get("type") != "auth" or not data.get("ticket"):
            await websocket.close(code=1008, reason="Unauthorized")
            return
        # Ticket was scoped with task_id=user_id
        authenticated_user = consume_ws_ticket(str(data["ticket"]), expected_task_id=user_id)
        if not authenticated_user or authenticated_user != user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        await user_call_notification_manager.connect(user_id, websocket)
        await user_call_notification_loop(user_id=user_id, websocket=websocket)
    except (TimeoutError, asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(code=1008, reason="Unauthorized")
    except Exception:
        user_call_notification_manager.disconnect(user_id, websocket)
        await websocket.close(code=1011, reason="Server error")


app.include_router(api_router, prefix=settings.api_prefix)
