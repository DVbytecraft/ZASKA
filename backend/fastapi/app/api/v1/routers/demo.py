"""Demo session endpoint — creates an ephemeral demo account on demand.

POST /demo/session
  No authentication required.
  Rate-limited to 5 sessions/IP/hour via Redis (fail-open if Redis is down).
  Returns a 2-hour access JWT and a pre-seeded 10 000 XOF wallet.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.responses import success_response
from app.db.session import get_db
from app.services.demo_service import bootstrap_demo_user

router = APIRouter(prefix="/demo", tags=["demo"])
logger = logging.getLogger(__name__)

_RATE_LIMIT = 5
_RATE_WINDOW = 3600  # 1 hour


@router.post("/session")
def create_demo_session(request: Request, db: Session = Depends(get_db)) -> dict:
    """Return a 2-hour demo JWT with 10 000 XOF pre-seeded.

    Each call creates a fresh isolated demo user — no shared state between sessions.
    Demo data is wiped every 24 h by the scheduler.
    """
    # ── IP-based rate limit (fail-open on Redis error) ────────────────────────
    client_ip = (
        request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
        or (request.client.host if request.client else "unknown")
    )
    try:
        from app.core.redis_client import redis_sync

        rate_key = f"demo_rate:{client_ip}"
        count = redis_sync.incr(rate_key)
        if count == 1:
            redis_sync.expire(rate_key, _RATE_WINDOW)
        if count > _RATE_LIMIT:
            raise HTTPException(
                status_code=429,
                detail="Trop de sessions démo. Réessayez dans une heure.",
            )
    except HTTPException:
        raise
    except Exception:
        pass  # Redis down — allow the request

    # ── Bootstrap demo user ───────────────────────────────────────────────────
    try:
        result = bootstrap_demo_user(db)
    except Exception as exc:
        logger.error("demo_session: bootstrap failed — %s", exc)
        raise HTTPException(
            status_code=500,
            detail="Impossible de créer la session démo. Réessayez dans quelques instants.",
        ) from exc

    return success_response(result)
