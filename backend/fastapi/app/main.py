import asyncio
import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import sentry_sdk
from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1.api import api_router
from app.api.websocket import (
    call_signaling_manager,
    call_signaling_loop,
    chat_ws_manager,
    user_call_notification_loop,
    user_call_notification_manager,
    websocket_loop,
)
from app.core.config import settings
from app.core.idempotency_middleware import IdempotencyMiddleware
from app.middleware.device_fingerprint import DeviceFingerprintMiddleware
from app.core.observability import RequestIDMiddleware, logger
from app.core.rate_limit import RedisRateLimitMiddleware
from app.core.responses import error_response, success_response
from app.core.scheduler import start_scheduler, stop_scheduler
from app.core.ws_ticket import consume_ws_ticket
from app.db.base import Base
from app.db.session import engine
from app.models import (  # noqa: F401
    aml,
    accounting,
    access_control,
    audit_log,
    b2b,
    call_session,
    chat_message,
    dispute,
    feature_flag,
    food,
    geography,
    kyc,
    location_config,
    module_control,
    negotiation_event,
    notification,
    outbox_event,
    payment_method,
    payout,
    referral,
    shop,
    social_protection,
    subscription,
    support_ticket,
    task,
    task_application,
    task_completion_code,
    trust,
    user,
    user_address,
    virtual_card,
    vtc,
    wallet,
    webhook_idempotency,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _validate_production_hard_lock() -> None:
    """Refuse to start in production if critical financial or security config is missing.

    These checks run at startup — the pod will crash immediately rather than
    silently serving requests with broken financial invariants.
    """
    env_norm = str(settings.env).strip().lower()
    mode = str(settings.payment_mode).strip().lower()

    # JWT_SECRET length (applies to all environments — already validated in config.py,
    # but we double-check here so startup fails loudly even if config.py is bypassed)
    if len(settings.jwt_secret.strip()) < 32:
        raise RuntimeError(
            f"CRITICAL: JWT_SECRET is only {len(settings.jwt_secret.strip())} chars. "
            "Minimum 32 required. Tokens can be forged with a weak secret."
        )

    if mode != "production":
        return

    # ZASKA_WALLET_USER_ID: without this, 15% commission on every escrow release is
    # silently discarded. At 1000 transactions/day this is significant financial loss.
    if not settings.zaska_wallet_user_id.strip():
        raise RuntimeError(
            "CRITICAL: ZASKA_WALLET_USER_ID is not set. "
            "Platform commission (15%) cannot be credited — every escrow release loses money. "
            "Configure this before handling real payments."
        )

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown (replaces deprecated @app.on_event)."""
    # ── Startup ──────────────────────────────────────────────────────────
    logger.info("ZASKA CORE OS startup env={} version=core-os-1.0", settings.env)
    if settings.sentry_dsn.strip():
        sentry_sdk.init(dsn=settings.sentry_dsn, traces_sample_rate=0.1, environment=settings.env)
    _validate_production_hard_lock()
    if settings.sqlite_auto_create_schema and settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(bind=engine)
        logger.info("ZASKA sqlite schema auto-created")
    # Chat Redis pub/sub subscriber (cross-instance chat delivery)
    if settings.realtime_enabled:
        redis_bridge_enabled = True
        try:
            from app.core.redis_client import redis_sync
            redis_sync.ping()
        except Exception as exc:
            redis_bridge_enabled = False
            logger.warning("ZASKA realtime Redis bridge disabled - %s", exc)

        chat_ws_manager.redis_bridge_enabled = redis_bridge_enabled
        user_call_notification_manager.redis_bridge_enabled = redis_bridge_enabled
        call_signaling_manager.redis_bridge_enabled = redis_bridge_enabled
        await chat_ws_manager.start()
        # User call notification Redis pub/sub subscriber
        await user_call_notification_manager.start()
        # WebRTC signaling cross-instance relay subscriber (SC-03 fix)
        await call_signaling_manager.start()
    else:
        logger.warning("ZASKA realtime disabled by configuration")
    # In-process scheduler with distributed Redis locks
    if settings.scheduler_enabled:
        start_scheduler()
    else:
        logger.warning("ZASKA scheduler disabled by configuration")

    # Seed trust catalog — idempotent, skips rows that already exist.
    # Badges and skills tables would be empty on first boot without this.
    from app.db.session import SessionLocal
    from app.services.access_control_service import AccessControlService
    from app.services.accounting_ledger_service import AccountingLedgerService
    from app.services.aml_service import AmlService
    from app.services.country_rollout_service import CountryRolloutService
    from app.services.geo_hierarchy_service import GeoHierarchyService
    from app.services.internal_wallet_seed_service import InternalWalletSeedService
    from app.services.module_control_service import ModuleControlService
    from app.services.referral_service import ReferralService
    from app.services.subscription_service import SubscriptionService
    from app.services.trust_service import TrustService
    _seed_db = SessionLocal()
    try:
        InternalWalletSeedService(_seed_db).ensure_all()
        logger.info("ZASKA internal wallet identities seeded")
        AccessControlService(_seed_db).seed_catalog()
        logger.info("ZASKA access control catalog seeded")
        _ = AmlService(_seed_db)
        AccountingLedgerService(_seed_db).seed_chart_of_accounts()
        logger.info("ZASKA accounting chart seeded")
        CountryRolloutService(_seed_db).seed_catalog()
        logger.info("ZASKA world country catalog seeded")
        GeoHierarchyService(_seed_db).seed_catalog()
        logger.info("ZASKA geography catalog seeded")
        ModuleControlService(_seed_db).seed_catalog()
        logger.info("ZASKA module catalog seeded")
        ReferralService(_seed_db).seed_catalog()
        logger.info("ZASKA referral catalog seeded")
        SubscriptionService(_seed_db).seed_catalog()
        logger.info("ZASKA subscription catalog seeded")
        TrustService(_seed_db).seed_catalog()
        logger.info("ZASKA trust catalog seeded")
    except Exception as _seed_err:
        logger.error("trust_catalog:seed_failed error={}", _seed_err)
    finally:
        _seed_db.close()

    yield

    # ── Shutdown ─────────────────────────────────────────────────────────
    if settings.scheduler_enabled:
        stop_scheduler()


# Public demo endpoints (P4): allocation simulator embedded on the public ZASKA
# website, served from any origin. They carry no auth/session, so a wildcard
# Access-Control-Allow-Origin (without credentials) is safe and intentional —
# this overrides the stricter, allowlist-based CORSMiddleware below for these
# paths only.
_PUBLIC_DEMO_PATHS = frozenset(
    {
        f"{settings.api_prefix}/v1/simulate-allocation",
        f"{settings.api_prefix}/v1/allocation-rules",
        f"{settings.api_prefix}/v1/calculate-benefits",
    }
)


class PublicDemoCORSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.url.path not in _PUBLIC_DEMO_PATHS:
            return await call_next(request)

        if request.method == "OPTIONS":
            response = Response(status_code=200)
        else:
            response = await call_next(request)

        response.headers["Access-Control-Allow-Origin"] = "*"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        if "Access-Control-Allow-Credentials" in response.headers:
            del response.headers["Access-Control-Allow-Credentials"]
        return response


app = FastAPI(title=settings.app_name, lifespan=lifespan)

_CORS_ALLOWED_ORIGINS = [origin.strip() for origin in settings.cors_allowed_origins.split(",") if origin.strip()]

app.add_middleware(IdempotencyMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(DeviceFingerprintMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Country-Code", "X-Request-ID", "X-Idempotency-Key", "X-Device-ID"],
)
app.add_middleware(
    RedisRateLimitMiddleware,
    max_requests=settings.rate_limit_max_requests,
    window_seconds=settings.rate_limit_window_seconds,
)
app.add_middleware(PublicDemoCORSMiddleware)


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
    if env_norm == "production":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    if "server" in response.headers:
        del response.headers["server"]
    return response


@app.get("/", include_in_schema=False)
def root():
    return success_response({"status": "ok", "service": settings.app_name, "environment": settings.env})


@app.get("/health")
def health():
    return success_response({"status": "ok"})


@app.get("/health/ready")
def health_ready():
    """Strict readiness check — fails if any critical financial config is missing.

    Used by Kubernetes readiness probe and load balancers.
    Returns 503 if the instance should NOT receive production traffic.

    Checks:
      - DB connectivity
      - Redis connectivity
      - ZASKA_WALLET_USER_ID configured (prevents silent commission loss)
      - JWT_SECRET strength
    """
    issues: list[str] = []

    # DB check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        issues.append(f"db_unreachable: {exc}")

    # Redis check
    try:
        from app.core.redis_client import redis_sync
        if not redis_sync.ping():
            issues.append("redis_ping_failed")
    except Exception as exc:
        issues.append(f"redis_unreachable: {exc}")

    # ZASKA_WALLET_USER_ID — must be set before handling real money
    if not settings.zaska_wallet_user_id.strip():
        issues.append("zaska_wallet_user_id_missing: 15% commission will be lost on every escrow release")

    # JWT_SECRET strength
    if len(settings.jwt_secret.strip()) < 32:
        issues.append(f"jwt_secret_too_short: {len(settings.jwt_secret.strip())} chars < 32 minimum")

    if issues:
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "issues": issues},
        )
    return success_response({"status": "ready"})


@app.get("/health/db")
def health_db():
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return success_response({"status": "ok"})


@app.get("/health/scheduler")
def health_scheduler():
    from app.core.scheduler import get_scheduler_health
    jobs = get_scheduler_health()
    dead = [name for name, info in jobs.items() if info.get("status") == "dead"]
    overall = "degraded" if dead else "ok"
    return success_response({"status": overall, "dead_jobs": dead, "jobs": jobs})


@app.get("/health/redis")
def health_redis():
    from app.core.redis_client import redis_sync
    try:
        pong = redis_sync.ping()
        if not pong:
            return JSONResponse(status_code=503, content=error_response("Redis ping failed"))
        return success_response({"status": "ok"})
    except Exception as exc:
        return JSONResponse(status_code=503, content=error_response(f"Redis unavailable: {exc}"))


@app.get("/health/realtime")
def health_realtime():
    from app.core.scheduler import get_scheduler_health, _tasks
    scheduler_running = len(_tasks) > 0
    jobs = get_scheduler_health()
    dead_jobs = [name for name, info in jobs.items() if info.get("status") == "dead"]

    ws_chat_connections = sum(
        len(conns) for conns in chat_ws_manager.connections.values()
    )
    call_rooms_active = len(call_signaling_manager.rooms)

    # Realtime health should reflect the websocket/call transport plane.
    # Batch scheduler drift is already exposed in /health/scheduler and should
    # not make realtime readiness fail when chat/call signaling is otherwise up.
    status = "ok" if scheduler_running else "degraded"
    return success_response({
        "status": status,
        "scheduler_running": scheduler_running,
        "scheduler_dead_jobs": dead_jobs,
        "ws_chat_connections": ws_chat_connections,
        "call_rooms_active": call_rooms_active,
    })


@app.get("/health/ops")
def health_ops():
    from app.db.session import SessionLocal
    from app.services.operations_resilience_service import OperationsResilienceService

    db = SessionLocal()
    try:
        snapshot = OperationsResilienceService(db).get_health_snapshot()
        return success_response(snapshot)
    finally:
        db.close()


@app.get("/health/backend-readiness")
def health_backend_readiness():
    from app.services.production_readiness_service import ProductionReadinessService

    report = ProductionReadinessService().build_report()
    return success_response(report)


@app.get("/health/metrics")
async def health_metrics():
    """Prometheus-compatible plain text metrics endpoint.

    The outbox query result is cached for 30s in Redis to avoid opening a new
    DB session on every Prometheus scrape (default: every 15s).
    """
    from app.core.redis_client import redis_async as r
    from app.core.scheduler import get_scheduler_health, _job_heartbeats
    from fastapi.responses import PlainTextResponse

    lines = []

    def gauge(name: str, value: float | int, labels: str = "") -> None:
        label_str = f"{{{labels}}}" if labels else ""
        lines.append(f"{name}{label_str} {value}")

    now = _utcnow()
    for job_name, last_run in _job_heartbeats.items():
        silence = (now - last_run).total_seconds()
        gauge("zaska_scheduler_job_silence_seconds", silence, f'job="{job_name}"')

    # Outbox metrics — cached 30s to avoid a DB hit on every scrape
    try:
        _CACHE_KEY = "metrics:outbox_cache"
        cached_raw = await r.get(_CACHE_KEY)
        if cached_raw:
            outbox_rows = json.loads(cached_raw)
        else:
            from app.db.session import SessionLocal
            db = SessionLocal()
            try:
                from sqlalchemy import text as sql_text
                rows = db.execute(sql_text(
                    "SELECT status, COUNT(*) as cnt FROM outbox_events GROUP BY status"
                )).all()
                outbox_rows = [{"status": row.status, "cnt": row.cnt} for row in rows]
                await r.setex(_CACHE_KEY, 30, json.dumps(outbox_rows))
            finally:
                db.close()
        for row in outbox_rows:
            gauge("zaska_outbox_events_total", row["cnt"], f'status="{row["status"]}"')
    except Exception:
        pass

    # Redis stats (async — non-blocking)
    try:
        info = await r.info("stats")
        gauge("zaska_redis_commands_processed_total", info.get("total_commands_processed", 0))
        gauge("zaska_redis_connected_clients", info.get("connected_clients", 0))
    except Exception:
        gauge("zaska_redis_up", 0)

    ws_connections = sum(len(c) for c in chat_ws_manager.connections.values())
    gauge("zaska_ws_chat_connections_active", ws_connections)
    gauge("zaska_call_rooms_active", len(call_signaling_manager.rooms))

    return PlainTextResponse("\n".join(lines), media_type="text/plain; version=0.0.4")


def _with_cors_headers(request, response: JSONResponse) -> JSONResponse:
    """Echo CORS headers onto error responses.

    Starlette's ServerErrorMiddleware (which dispatches the generic
    `Exception` handler below) sits OUTSIDE CORSMiddleware, so 500 responses
    never pass through it and arrive at the browser with no
    Access-Control-Allow-Origin header — the browser then reports a
    misleading "CORS error" that hides the real 500. Re-applying the same
    allowlist check here ensures error responses are still readable
    cross-origin.
    """
    origin = request.headers.get("origin")
    if origin and origin in _CORS_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Vary"] = "Origin"
    return response


@app.exception_handler(StarletteHTTPException)
async def starlette_http_exception_handler(request, exc: StarletteHTTPException):
    return _with_cors_headers(request, JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail))))


@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc: HTTPException):
    return _with_cors_headers(request, JSONResponse(status_code=exc.status_code, content=error_response(str(exc.detail))))


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    return _with_cors_headers(request, JSONResponse(status_code=422, content=error_response("Invalid request payload", exc.errors())))


@app.exception_handler(Exception)
async def generic_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception: {}", exc)
    return _with_cors_headers(request, JSONResponse(status_code=500, content=error_response("Internal server error")))


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
        accepted = await call_signaling_manager.connect(call_id, websocket, user_id)
        if not accepted:
            await websocket.close(code=1008, reason="Call room full")
            return
        await call_signaling_manager.drain_signal_queue(call_id, websocket)
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
        authenticated_user = consume_ws_ticket(str(data["ticket"]), expected_task_id=user_id)
        if not authenticated_user or authenticated_user != user_id:
            await websocket.close(code=1008, reason="Unauthorized")
            return
        accepted = await user_call_notification_manager.connect(user_id, websocket)
        if not accepted:
            await websocket.close(code=1008, reason="Server at capacity")
            return
        await user_call_notification_loop(user_id=user_id, websocket=websocket)
    except (TimeoutError, asyncio.TimeoutError, json.JSONDecodeError):
        await websocket.close(code=1008, reason="Unauthorized")
    except Exception:
        user_call_notification_manager.disconnect(user_id, websocket)
        await websocket.close(code=1011, reason="Server error")


app.include_router(api_router, prefix=settings.api_prefix)
