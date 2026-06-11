from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.food import FoodOrder
from app.models.shop import ShopOrder
from app.models.vtc import VtcRideDispatchOffer, VtcRideRequest
from app.services.vtc_service import VtcService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class OperationsResilienceService:
    def __init__(self, db: Session):
        self.db = db

    def run_cycle(self) -> dict[str, int]:
        expired_vtc_offers = self._expire_stale_vtc_offers()
        redispatched_vtc_rides = self._redispatch_stale_vtc_rides()
        stale_shop_orders = self._mark_stale_shop_orders()
        stale_food_orders = self._mark_stale_food_orders()
        self.db.commit()
        return {
            "expired_vtc_offers": expired_vtc_offers,
            "redispatched_vtc_rides": redispatched_vtc_rides,
            "stale_shop_orders": stale_shop_orders,
            "stale_food_orders": stale_food_orders,
        }

    def get_health_snapshot(self) -> dict[str, object]:
        now = _utcnow()
        ride_cutoff = now - timedelta(minutes=5)
        order_cutoff = now - timedelta(minutes=30)
        food_cutoff = now - timedelta(minutes=45)

        stale_vtc_rides = self.db.execute(
            select(VtcRideRequest).where(
                VtcRideRequest.status.in_(["searching_driver", "no_driver_available"]),
                VtcRideRequest.created_at <= ride_cutoff,
            )
        ).scalars().all()

        pending_shop_orders = self.db.execute(
            select(ShopOrder).where(
                ShopOrder.status.in_(["merchant_pending_confirmation", "ready_for_dispatch"]),
                ShopOrder.created_at <= order_cutoff,
            )
        ).scalars().all()

        pending_food_orders = self.db.execute(
            select(FoodOrder).where(
                FoodOrder.status.in_(["pending", "restaurant_confirmed", "ready_for_dispatch"]),
                FoodOrder.created_at <= food_cutoff,
            )
        ).scalars().all()

        return {
            "status": "degraded" if stale_vtc_rides or pending_shop_orders or pending_food_orders else "ok",
            "vtc": {
                "staleRides": len(stale_vtc_rides),
                "staleRideIds": [row.id for row in stale_vtc_rides[:20]],
            },
            "shop": {
                "staleOrders": len(pending_shop_orders),
                "staleOrderIds": [row.id for row in pending_shop_orders[:20]],
            },
            "food": {
                "staleOrders": len(pending_food_orders),
                "staleOrderIds": [row.id for row in pending_food_orders[:20]],
            },
        }

    def _expire_stale_vtc_offers(self) -> int:
        now = _utcnow()
        offers = self.db.execute(
            select(VtcRideDispatchOffer).where(
                VtcRideDispatchOffer.status == "pending",
                VtcRideDispatchOffer.expires_at.is_not(None),
                VtcRideDispatchOffer.expires_at <= now,
            )
        ).scalars().all()
        count = 0
        for offer in offers:
            offer.status = "expired"
            offer.responded_at = now
            count += 1
        return count

    def _redispatch_stale_vtc_rides(self) -> int:
        now = _utcnow()
        cutoff = now - timedelta(minutes=2)
        rides = self.db.execute(
            select(VtcRideRequest).where(
                VtcRideRequest.status.in_(["searching_driver", "no_driver_available"]),
                VtcRideRequest.driver_user_id.is_(None),
                VtcRideRequest.created_at <= cutoff,
            )
        ).scalars().all()
        count = 0
        service = VtcService(self.db)
        for ride in rides:
            try:
                service.dispatch_ride(ride_id=ride.id)
                count += 1
            except Exception:
                continue
        return count

    def _mark_stale_shop_orders(self) -> int:
        cutoff = _utcnow() - timedelta(minutes=30)
        orders = self.db.execute(
            select(ShopOrder).where(
                ShopOrder.status == "merchant_pending_confirmation",
                ShopOrder.created_at <= cutoff,
            )
        ).scalars().all()
        count = 0
        for order in orders:
            payload = {}
            if order.metadata_json:
                try:
                    payload = __import__("json").loads(order.metadata_json) or {}
                except Exception:
                    payload = {}
            if not payload.get("ops_stale_flagged"):
                payload["ops_stale_flagged"] = True
                payload["ops_stale_flagged_at"] = _utcnow().isoformat()
                order.metadata_json = __import__("json").dumps(payload)
                count += 1
        return count

    def _mark_stale_food_orders(self) -> int:
        cutoff = _utcnow() - timedelta(minutes=45)
        orders = self.db.execute(
            select(FoodOrder).where(
                FoodOrder.status.in_(["pending", "restaurant_confirmed", "ready_for_dispatch"]),
                FoodOrder.created_at <= cutoff,
            )
        ).scalars().all()
        count = 0
        for order in orders:
            payload = {}
            if order.metadata_json:
                try:
                    payload = __import__("json").loads(order.metadata_json) or {}
                except Exception:
                    payload = {}
            if not payload.get("ops_stale_flagged"):
                payload["ops_stale_flagged"] = True
                payload["ops_stale_flagged_at"] = _utcnow().isoformat()
                order.metadata_json = __import__("json").dumps(payload)
                count += 1
        return count
