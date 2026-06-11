from __future__ import annotations

import json
import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.user import User
from app.models.vtc import (
    VtcDriverProfile,
    VtcFleetOperator,
    VtcRideDispatchOffer,
    VtcRideEvent,
    VtcRideRequest,
    VtcVehicle,
)
from app.models.wallet import Wallet
from app.services.country_rollout_service import CountryRolloutService
from app.services.pricing_engine_service import PricingEngineService
from app.services.wallet_service import WalletService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _to_decimal(value: Decimal | float | int | str | None, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


class VtcService:
    def __init__(self, db: Session):
        self.db = db
        self.pricing_service = PricingEngineService(db)

    def create_driver_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        country_code: str,
        phone: str | None = None,
    ) -> dict:
        email_norm = email.strip().lower()
        existing = self.db.execute(select(User).where(User.email == email_norm)).scalars().one_or_none()
        if existing is not None:
            raise ValueError("Email déjà utilisé")
        user = User(
            id=str(uuid.uuid4()),
            email=email_norm,
            phone=phone.strip() if phone else None,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}".strip(),
            password_hash=get_password_hash(password),
            role="driver",
            is_verified=True,
            country_code=country_code.upper(),
        )
        self.db.add(user)
        self.db.flush()
        self._ensure_wallets(user.id, user.country_code)
        self.db.commit()
        self.db.refresh(user)
        CountryRolloutService(self.db).ensure_country(user.country_code)
        return self._serialize_user(user)

    def create_operator(
        self,
        *,
        public_name: str,
        country_code: str,
        city_name: str,
        currency: str,
        owner_user_id: str | None = None,
        service_zone_id: str | None = None,
        legal_name: str | None = None,
        description: str | None = None,
        phone: str | None = None,
        email: str | None = None,
        is_active: bool = True,
        accepting_rides: bool = True,
        launch_status: str = "CONFIGURED",
        metadata: dict | None = None,
    ) -> dict:
        item = VtcFleetOperator(
            owner_user_id=owner_user_id,
            service_zone_id=service_zone_id,
            public_name=public_name,
            legal_name=legal_name,
            description=description,
            country_code=country_code.upper(),
            city_name=city_name,
            currency=currency.upper(),
            phone=phone,
            email=email,
            is_active=is_active,
            accepting_rides=accepting_rides,
            launch_status=launch_status,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_operator(item)

    def list_operators(
        self,
        *,
        country_code: str | None = None,
        city_name: str | None = None,
        active_only: bool = False,
        limit: int | None = None,
    ) -> list[dict]:
        stmt = select(VtcFleetOperator).order_by(desc(VtcFleetOperator.created_at))
        if country_code:
            stmt = stmt.where(VtcFleetOperator.country_code == country_code.upper())
        if city_name:
            stmt = stmt.where(VtcFleetOperator.city_name.ilike(f"%{city_name.strip()}%"))
        if active_only:
            stmt = stmt.where(VtcFleetOperator.is_active.is_(True), VtcFleetOperator.accepting_rides.is_(True))
        rows = self.db.execute(stmt).scalars().all()
        payload = [self._serialize_operator(row) for row in rows]
        return payload[:limit] if limit else payload

    def create_driver_profile(
        self,
        *,
        user_id: str,
        operator_id: str | None = None,
        license_number: str | None = None,
        license_country_code: str | None = None,
        license_expires_at: datetime | None = None,
        vehicle_ready: bool = False,
        is_active: bool = True,
        verification_status: str = "pending",
        metadata: dict | None = None,
    ) -> dict:
        if self.db.get(User, user_id) is None:
            raise ValueError("Utilisateur chauffeur introuvable")
        if operator_id and self.db.get(VtcFleetOperator, operator_id) is None:
            raise ValueError("Opérateur introuvable")
        existing = self.db.execute(select(VtcDriverProfile).where(VtcDriverProfile.user_id == user_id)).scalars().one_or_none()
        if existing is not None:
            raise ValueError("Profil chauffeur déjà existant")
        item = VtcDriverProfile(
            user_id=user_id,
            operator_id=operator_id,
            license_number=license_number,
            license_country_code=license_country_code.upper() if license_country_code else None,
            license_expires_at=license_expires_at,
            vehicle_ready=vehicle_ready,
            is_active=is_active,
            verification_status=verification_status,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_driver_profile(item)

    def list_driver_profiles(
        self,
        *,
        operator_id: str | None = None,
        user_id: str | None = None,
        online_only: bool = False,
    ) -> list[dict]:
        stmt = select(VtcDriverProfile).order_by(desc(VtcDriverProfile.created_at))
        if operator_id:
            stmt = stmt.where(VtcDriverProfile.operator_id == operator_id)
        if user_id:
            stmt = stmt.where(VtcDriverProfile.user_id == user_id)
        if online_only:
            stmt = stmt.where(VtcDriverProfile.is_online.is_(True))
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_driver_profile(row) for row in rows]

    def create_vehicle(
        self,
        *,
        make: str,
        model: str,
        plate_number: str,
        seats_count: int,
        operator_id: str | None = None,
        driver_user_id: str | None = None,
        color: str | None = None,
        category: str = "standard",
        is_active: bool = True,
        verification_status: str = "pending",
        metadata: dict | None = None,
    ) -> dict:
        if operator_id and self.db.get(VtcFleetOperator, operator_id) is None:
            raise ValueError("Opérateur introuvable")
        if driver_user_id and self.db.get(User, driver_user_id) is None:
            raise ValueError("Chauffeur introuvable")
        item = VtcVehicle(
            operator_id=operator_id,
            driver_user_id=driver_user_id,
            make=make,
            model=model,
            color=color,
            plate_number=plate_number,
            category=category,
            seats_count=seats_count,
            is_active=is_active,
            verification_status=verification_status,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_vehicle(item)

    def list_vehicles(self, *, operator_id: str | None = None, driver_user_id: str | None = None) -> list[dict]:
        stmt = select(VtcVehicle).order_by(desc(VtcVehicle.created_at))
        if operator_id:
            stmt = stmt.where(VtcVehicle.operator_id == operator_id)
        if driver_user_id:
            stmt = stmt.where(VtcVehicle.driver_user_id == driver_user_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_vehicle(row) for row in rows]

    def create_ride_request(
        self,
        *,
        customer_user_id: str,
        pickup_address: str,
        destination_address: str,
        currency: str,
        operator_id: str | None = None,
        driver_user_id: str | None = None,
        linked_task_id: str | None = None,
        pickup_latitude: float | None = None,
        pickup_longitude: float | None = None,
        destination_latitude: float | None = None,
        destination_longitude: float | None = None,
        scheduled_at: datetime | None = None,
        estimated_distance_km: Decimal | None = None,
        estimated_duration_minutes: int | None = None,
        estimated_fare: Decimal | None = None,
        passenger_name: str | None = None,
        passenger_phone: str | None = None,
        ride_type: str = "standard",
        customer_note: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        customer = self.db.get(User, customer_user_id)
        if customer is None:
            raise ValueError("Client introuvable")
        operator = self._load_operator(operator_id) if operator_id else None
        if operator and (not operator.is_active or not operator.accepting_rides):
            raise ValueError("Cet opérateur n'accepte pas de courses actuellement")
        if driver_user_id and self.db.get(User, driver_user_id) is None:
            raise ValueError("Chauffeur introuvable")

        quote = self._build_quote(
            operator=operator,
            currency=currency,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            estimated_distance_km=estimated_distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_fare=estimated_fare,
            ride_type=ride_type,
        )
        now = _utcnow()
        item = VtcRideRequest(
            customer_user_id=customer_user_id,
            operator_id=operator_id,
            driver_user_id=driver_user_id,
            linked_task_id=linked_task_id,
            ride_code=self._generate_ride_code(),
            pickup_address=pickup_address,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_address=destination_address,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            scheduled_at=scheduled_at,
            requested_at=now,
            estimated_distance_km=estimated_distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_fare=quote["quotedFare"],
            quoted_fare=quote["quotedFare"],
            base_fare_amount=quote["baseFareAmount"],
            distance_fare_amount=quote["distanceFareAmount"],
            time_fare_amount=quote["timeFareAmount"],
            surge_multiplier=quote["surgeMultiplier"],
            platform_fee_amount=quote["platformFeeAmount"],
            driver_payout_amount=quote["driverPayoutAmount"],
            currency=currency.upper(),
            status="searching_driver" if driver_user_id is None else "driver_assigned",
            dispatch_status="pending" if driver_user_id is None else "assigned_manually",
            driver_offer_expires_at=now + timedelta(seconds=60) if driver_user_id is None else None,
            ride_type=ride_type,
            passenger_name=passenger_name,
            passenger_phone=passenger_phone,
            customer_note=customer_note,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(item)
        self.db.flush()

        self._append_ride_event(
            ride=item,
            event_type="ride_requested",
            actor_user_id=customer_user_id,
            note="Course demandée",
            payload={"rideType": ride_type, "scheduledAt": scheduled_at.isoformat() if scheduled_at else None},
        )

        if driver_user_id:
            self._assign_driver_to_ride(
                ride=item,
                driver_user_id=driver_user_id,
                assignment_mode="direct",
                actor_user_id=customer_user_id,
            )
        else:
            self._dispatch_ride_internal(item)

        self.db.commit()
        self.db.refresh(item)
        return self.get_ride_detail(item.id)

    def quote_ride_request(
        self,
        *,
        operator_id: str | None,
        currency: str,
        ride_type: str,
        pickup_latitude: float | None,
        pickup_longitude: float | None,
        destination_latitude: float | None,
        destination_longitude: float | None,
        estimated_distance_km: Decimal | None = None,
        estimated_duration_minutes: int | None = None,
        estimated_fare: Decimal | None = None,
    ) -> dict[str, object]:
        operator = self._load_operator(operator_id) if operator_id else None
        quote = self._build_quote(
            operator=operator,
            currency=currency,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            estimated_distance_km=estimated_distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_fare=estimated_fare,
            ride_type=ride_type,
        )
        return self.pricing_service.serialize_quote(quote)

    def list_rides(
        self,
        *,
        customer_user_id: str | None = None,
        operator_id: str | None = None,
        driver_user_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        stmt = select(VtcRideRequest).order_by(desc(VtcRideRequest.created_at))
        if customer_user_id:
            stmt = stmt.where(VtcRideRequest.customer_user_id == customer_user_id)
        if operator_id:
            stmt = stmt.where(VtcRideRequest.operator_id == operator_id)
        if driver_user_id:
            stmt = stmt.where(VtcRideRequest.driver_user_id == driver_user_id)
        if status:
            stmt = stmt.where(VtcRideRequest.status == status)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_ride(row) for row in rows]

    def get_ride_detail(self, ride_id: str) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None:
            raise ValueError("Course introuvable")
        data = self._serialize_ride(ride)
        offers = self.db.execute(
            select(VtcRideDispatchOffer)
            .where(VtcRideDispatchOffer.ride_id == ride_id)
            .order_by(VtcRideDispatchOffer.offered_at.desc())
        ).scalars().all()
        events = self.db.execute(
            select(VtcRideEvent)
            .where(VtcRideEvent.ride_id == ride_id)
            .order_by(VtcRideEvent.created_at.asc())
        ).scalars().all()
        data["offers"] = [self._serialize_offer(item) for item in offers]
        data["events"] = [self._serialize_event(item) for item in events]
        return data

    def update_driver_presence(
        self,
        *,
        user_id: str,
        is_online: bool,
        latitude: float | None = None,
        longitude: float | None = None,
        operator_id: str | None = None,
    ) -> dict:
        profile = self._load_driver_profile(user_id, for_update=True)
        if operator_id:
            if self.db.get(VtcFleetOperator, operator_id) is None:
                raise ValueError("Opérateur introuvable")
            profile.operator_id = operator_id
        if is_online:
            self._ensure_driver_is_dispatch_ready(user_id, profile)
            if profile.current_ride_id:
                profile.availability_status = "busy"
                profile.is_online = True
            else:
                profile.availability_status = "online"
                profile.is_online = True
        else:
            if profile.current_ride_id:
                raise ValueError("Impossible de passer hors ligne pendant une course active")
            profile.availability_status = "offline"
            profile.is_online = False
        if latitude is not None:
            profile.current_latitude = latitude
        if longitude is not None:
            profile.current_longitude = longitude
        if latitude is not None or longitude is not None:
            profile.last_location_at = _utcnow()
        self.db.commit()
        self.db.refresh(profile)
        return self._serialize_driver_profile(profile)

    def update_driver_location(
        self,
        *,
        user_id: str,
        latitude: float,
        longitude: float,
        heading: float | None = None,
    ) -> dict:
        profile = self._load_driver_profile(user_id, for_update=True)
        profile.current_latitude = latitude
        profile.current_longitude = longitude
        profile.last_location_at = _utcnow()
        active_ride = None
        if profile.current_ride_id:
            active_ride = self.db.get(VtcRideRequest, profile.current_ride_id)
        if active_ride is not None:
            active_ride.last_driver_latitude = latitude
            active_ride.last_driver_longitude = longitude
            active_ride.last_driver_heading = heading
            active_ride.last_driver_location_at = profile.last_location_at
        self.db.commit()
        self.db.refresh(profile)
        return {
            "driverProfile": self._serialize_driver_profile(profile),
            "activeRideId": active_ride.id if active_ride else None,
        }

    def list_driver_offers(self, *, user_id: str, include_expired: bool = False) -> list[dict]:
        stmt = select(VtcRideDispatchOffer).where(VtcRideDispatchOffer.driver_user_id == user_id)
        if not include_expired:
            stmt = stmt.where(VtcRideDispatchOffer.status.in_(["pending", "accepted"]))
        stmt = stmt.order_by(desc(VtcRideDispatchOffer.offered_at))
        offers = self.db.execute(stmt).scalars().all()
        now = _utcnow()
        changed = False
        for offer in offers:
            if offer.status == "pending" and offer.expires_at and offer.expires_at < now:
                offer.status = "expired"
                offer.responded_at = now
                changed = True
        if changed:
            self.db.commit()
        return [self._serialize_offer(item) for item in offers if include_expired or item.status in ("pending", "accepted")]

    def respond_to_offer(self, *, user_id: str, offer_id: str, accept: bool) -> dict:
        offer = self.db.get(VtcRideDispatchOffer, offer_id)
        if offer is None or offer.driver_user_id != user_id:
            raise ValueError("Offre introuvable")
        ride = self.db.get(VtcRideRequest, offer.ride_id)
        if ride is None:
            raise ValueError("Course introuvable")
        profile = self._load_driver_profile(user_id, for_update=True)
        now = _utcnow()
        if offer.status != "pending":
            raise ValueError("Cette offre n'est plus active")
        if offer.expires_at and offer.expires_at < now:
            offer.status = "expired"
            offer.responded_at = now
            self.db.commit()
            raise ValueError("Cette offre a expiré")

        if accept:
            self._ensure_driver_is_dispatch_ready(user_id, profile)
            self._assign_driver_to_ride(
                ride=ride,
                driver_user_id=user_id,
                assignment_mode="offer_accept",
                actor_user_id=user_id,
                accepted_offer=offer,
            )
        else:
            offer.status = "rejected"
            offer.responded_at = now
            self._append_ride_event(
                ride=ride,
                event_type="driver_offer_rejected",
                actor_user_id=user_id,
                note="Offre refusée",
                payload={"offerId": offer.id},
            )
            self._expire_other_stale_offers(ride.id)
            if not self._has_pending_offers(ride.id):
                self._dispatch_ride_internal(ride, exclude_driver_ids={user_id})
        self.db.commit()
        return self.get_ride_detail(ride.id)

    def list_driver_rides(self, *, user_id: str, status: str | None = None) -> list[dict]:
        return self.list_rides(driver_user_id=user_id, status=status)

    def dispatch_ride(self, *, ride_id: str) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None:
            raise ValueError("Course introuvable")
        self._dispatch_ride_internal(ride)
        self.db.commit()
        return self.get_ride_detail(ride_id)

    def admin_assign_driver(self, *, ride_id: str, driver_user_id: str, actor_user_id: str | None = None) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None:
            raise ValueError("Course introuvable")
        self._assign_driver_to_ride(
            ride=ride,
            driver_user_id=driver_user_id,
            assignment_mode="admin_assign",
            actor_user_id=actor_user_id,
        )
        self.db.commit()
        return self.get_ride_detail(ride_id)

    def update_ride_status_as_driver(
        self,
        *,
        user_id: str,
        ride_id: str,
        action: str,
        note: str | None = None,
        final_fare: Decimal | None = None,
        final_distance_km: Decimal | None = None,
        final_duration_minutes: int | None = None,
    ) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None or ride.driver_user_id != user_id:
            raise ValueError("Course introuvable")
        profile = self._load_driver_profile(user_id, for_update=True)
        now = _utcnow()

        if action == "en_route":
            self._require_ride_status(ride, {"driver_assigned"})
            ride.status = "driver_en_route"
            ride.driver_en_route_at = now
            self._append_ride_event(ride=ride, event_type="driver_en_route", actor_user_id=user_id, note=note or "Le chauffeur se dirige vers le point de départ")
        elif action == "arrived":
            self._require_ride_status(ride, {"driver_assigned", "driver_en_route"})
            ride.status = "driver_arrived"
            ride.driver_arrived_at = now
            self._append_ride_event(ride=ride, event_type="driver_arrived", actor_user_id=user_id, note=note or "Le chauffeur est arrivé")
        elif action == "start":
            self._require_ride_status(ride, {"driver_assigned", "driver_en_route", "driver_arrived"})
            ride.status = "in_progress"
            ride.started_at = now
            self._append_ride_event(ride=ride, event_type="ride_started", actor_user_id=user_id, note=note or "Course démarrée")
        elif action == "complete":
            self._require_ride_status(ride, {"in_progress", "driver_arrived"})
            ride.status = "completed"
            ride.completed_at = now
            if final_distance_km is not None:
                ride.estimated_distance_km = final_distance_km
            if final_duration_minutes is not None:
                ride.estimated_duration_minutes = final_duration_minutes
            self._finalize_ride_amounts(ride, final_fare=final_fare)
            profile.current_ride_id = None
            profile.availability_status = "online" if profile.is_online else "offline"
            profile.rides_completed_count = int(profile.rides_completed_count or 0) + 1
            self._append_ride_event(ride=ride, event_type="ride_completed", actor_user_id=user_id, note=note or "Course terminée")
            self.db.commit()
            return self.settle_ride_payout(ride_id=ride.id)
        elif action == "cancel":
            self._require_ride_status(ride, {"driver_assigned", "driver_en_route", "driver_arrived"})
            ride.status = "cancelled"
            ride.dispatch_status = "cancelled"
            ride.cancelled_at = now
            ride.cancelled_by_user_id = user_id
            ride.cancellation_reason = note or "Course annulée par le chauffeur"
            profile.current_ride_id = None
            profile.availability_status = "online" if profile.is_online else "offline"
            profile.rides_cancelled_count = int(profile.rides_cancelled_count or 0) + 1
            self._append_ride_event(ride=ride, event_type="ride_cancelled_by_driver", actor_user_id=user_id, note=ride.cancellation_reason)
        else:
            raise ValueError("Action chauffeur inconnue")

        self.db.commit()
        return self.get_ride_detail(ride_id)

    def cancel_ride_as_customer(self, *, user_id: str, ride_id: str, reason: str | None = None) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None or ride.customer_user_id != user_id:
            raise ValueError("Course introuvable")
        self._require_ride_status(ride, {"searching_driver", "driver_assigned", "driver_en_route"})
        ride.status = "cancelled"
        ride.dispatch_status = "cancelled"
        ride.cancelled_at = _utcnow()
        ride.cancelled_by_user_id = user_id
        ride.cancellation_reason = reason or "Course annulée par le client"
        self._release_driver_from_ride(ride.driver_user_id)
        for offer in self.db.execute(select(VtcRideDispatchOffer).where(VtcRideDispatchOffer.ride_id == ride.id)).scalars().all():
            if offer.status == "pending":
                offer.status = "cancelled"
                offer.responded_at = ride.cancelled_at
        self._append_ride_event(ride=ride, event_type="ride_cancelled_by_customer", actor_user_id=user_id, note=ride.cancellation_reason)
        self.db.commit()
        return self.get_ride_detail(ride_id)

    def settle_ride_payout(self, *, ride_id: str) -> dict:
        ride = self.db.get(VtcRideRequest, ride_id)
        if ride is None:
            raise ValueError("Course introuvable")
        if ride.status != "completed":
            raise ValueError("La course doit être terminée avant règlement")
        if not ride.driver_user_id:
            raise ValueError("Aucun chauffeur assigné")
        if ride.payout_status == "completed":
            return self.get_ride_detail(ride_id)
        payout_amount = _to_decimal(ride.driver_payout_amount, "0")
        if payout_amount <= Decimal("0"):
            ride.payout_status = "not_applicable"
            self.db.commit()
            return self.get_ride_detail(ride_id)

        wallet_service = WalletService(self.db)
        try:
            wallet_service.credit_wallet(
                user_id=ride.driver_user_id,
                currency=ride.currency,
                amount=payout_amount,
                reference=f"vtc_ride_payout:{ride.id}",
                metadata={
                    "module": "vtc",
                    "ride_id": ride.id,
                    "customer_user_id": ride.customer_user_id,
                },
            )
            ride.payout_status = "completed"
            ride.payout_completed_at = _utcnow()
            self._append_ride_event(
                ride=ride,
                event_type="driver_payout_completed",
                actor_user_id=None,
                note="Paiement chauffeur crédité",
                payload={"amount": str(payout_amount), "currency": ride.currency},
            )
            self.db.commit()
        except Exception as exc:
            ride.payout_status = "failed"
            self._append_ride_event(
                ride=ride,
                event_type="driver_payout_failed",
                actor_user_id=None,
                note=str(exc),
            )
            self.db.commit()
            raise
        return self.get_ride_detail(ride_id)

    def get_driver_dashboard(self, user_id: str) -> dict:
        profiles = self.list_driver_profiles(user_id=user_id)
        vehicles = self.list_vehicles(driver_user_id=user_id)
        rides = self.list_driver_rides(user_id=user_id)
        offers = self.list_driver_offers(user_id=user_id)
        operators = []
        operator_ids = {item["operatorId"] for item in profiles if item.get("operatorId")}
        for operator_id in operator_ids:
            operator = self.db.get(VtcFleetOperator, operator_id)
            if operator:
                operators.append(self._serialize_operator(operator))
        active_ride = next((item for item in rides if item["status"] in {"driver_assigned", "driver_en_route", "driver_arrived", "in_progress"}), None)
        return {
            "driverProfiles": profiles,
            "vehicles": vehicles,
            "rides": rides,
            "offers": offers,
            "operators": operators,
            "activeRide": active_ride,
        }

    def _dispatch_ride_internal(self, ride: VtcRideRequest, exclude_driver_ids: set[str] | None = None) -> None:
        exclude_driver_ids = exclude_driver_ids or set()
        if ride.status in {"cancelled", "completed"}:
            return
        now = _utcnow()
        candidates = self._list_dispatch_candidates(ride, exclude_driver_ids=exclude_driver_ids)
        if not candidates:
            ride.dispatch_status = "no_candidates"
            ride.status = "no_driver_available"
            ride.driver_offer_expires_at = None
            self._append_ride_event(
                ride=ride,
                event_type="dispatch_exhausted",
                actor_user_id=None,
                note="Aucun chauffeur disponible",
            )
            return

        ride.status = "searching_driver"
        ride.dispatch_status = "offered"
        ride.driver_offer_expires_at = now + timedelta(seconds=60)
        created = 0
        for candidate in candidates[:5]:
            existing = self.db.execute(
                select(VtcRideDispatchOffer).where(
                    VtcRideDispatchOffer.ride_id == ride.id,
                    VtcRideDispatchOffer.driver_user_id == candidate["driverUserId"],
                    VtcRideDispatchOffer.status.in_(["pending", "accepted"]),
                )
            ).scalars().one_or_none()
            if existing is not None:
                continue
            offer = VtcRideDispatchOffer(
                ride_id=ride.id,
                driver_user_id=candidate["driverUserId"],
                operator_id=candidate.get("operatorId"),
                vehicle_id=candidate.get("vehicleId"),
                status="pending",
                distance_to_pickup_km=candidate.get("distanceToPickupKm"),
                ranking_score=candidate.get("rankingScore"),
                expires_at=ride.driver_offer_expires_at,
                metadata_json=json.dumps(
                    {
                        "availabilityStatus": candidate.get("availabilityStatus"),
                    }
                ),
            )
            self.db.add(offer)
            created += 1
        self._append_ride_event(
            ride=ride,
            event_type="dispatch_offers_created",
            actor_user_id=None,
            note="Offres de course émises",
            payload={"offersCount": created},
        )

    def _list_dispatch_candidates(self, ride: VtcRideRequest, *, exclude_driver_ids: set[str]) -> list[dict]:
        stmt = select(VtcDriverProfile).where(
            VtcDriverProfile.is_active.is_(True),
            VtcDriverProfile.is_online.is_(True),
            VtcDriverProfile.vehicle_ready.is_(True),
            VtcDriverProfile.availability_status == "online",
            VtcDriverProfile.current_ride_id.is_(None),
            VtcDriverProfile.verification_status.in_(["approved", "verified"]),
        )
        if ride.operator_id:
            stmt = stmt.where(VtcDriverProfile.operator_id == ride.operator_id)
        profiles = self.db.execute(stmt.order_by(desc(VtcDriverProfile.last_location_at))).scalars().all()
        candidates: list[dict] = []
        for profile in profiles:
            if profile.user_id in exclude_driver_ids:
                continue
            user = self.db.get(User, profile.user_id)
            if user is None or user.is_suspended or user.is_locked or not user.is_verified:
                continue
            if not user.tasker_security_verified:
                continue
            if profile.license_expires_at and profile.license_expires_at <= _utcnow():
                continue
            vehicle = self.db.execute(
                select(VtcVehicle).where(
                    VtcVehicle.driver_user_id == profile.user_id,
                    VtcVehicle.is_active.is_(True),
                    VtcVehicle.verification_status.in_(["approved", "verified"]),
                )
            ).scalars().first()
            if vehicle is None:
                continue
            distance = self._distance_km(
                profile.current_latitude,
                profile.current_longitude,
                ride.pickup_latitude,
                ride.pickup_longitude,
            )
            ranking_score = Decimal("1000")
            if distance is not None:
                ranking_score = Decimal("1000") - distance
            candidates.append(
                {
                    "driverUserId": profile.user_id,
                    "operatorId": profile.operator_id,
                    "vehicleId": vehicle.id,
                    "availabilityStatus": profile.availability_status,
                    "distanceToPickupKm": distance,
                    "rankingScore": ranking_score.quantize(Decimal("0.000001")),
                }
            )
        candidates.sort(key=lambda item: (item["distanceToPickupKm"] is None, item["distanceToPickupKm"] or Decimal("999999")))
        return candidates

    def _assign_driver_to_ride(
        self,
        *,
        ride: VtcRideRequest,
        driver_user_id: str,
        assignment_mode: str,
        actor_user_id: str | None,
        accepted_offer: VtcRideDispatchOffer | None = None,
    ) -> None:
        profile = self._load_driver_profile(driver_user_id, for_update=True)
        self._ensure_driver_is_dispatch_ready(driver_user_id, profile)
        ride.driver_user_id = driver_user_id
        ride.status = "driver_assigned"
        ride.dispatch_status = "driver_assigned"
        ride.assigned_at = _utcnow()
        ride.accepted_at = ride.assigned_at
        ride.driver_offer_expires_at = None
        profile.current_ride_id = ride.id
        profile.availability_status = "busy"
        profile.is_online = True

        offers = self.db.execute(select(VtcRideDispatchOffer).where(VtcRideDispatchOffer.ride_id == ride.id)).scalars().all()
        for offer in offers:
            if offer.driver_user_id == driver_user_id:
                offer.status = "accepted" if accepted_offer is None or offer.id == accepted_offer.id else "cancelled"
                offer.responded_at = ride.assigned_at
            elif offer.status == "pending":
                offer.status = "expired"
                offer.responded_at = ride.assigned_at

        self._append_ride_event(
            ride=ride,
            event_type="driver_assigned",
            actor_user_id=actor_user_id,
            note="Chauffeur assigné",
            payload={"driverUserId": driver_user_id, "assignmentMode": assignment_mode},
        )

    def _ensure_driver_is_dispatch_ready(self, user_id: str, profile: VtcDriverProfile) -> None:
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("Chauffeur introuvable")
        if user.is_suspended or user.is_locked:
            raise ValueError("Le compte chauffeur n'est pas actif")
        if not user.is_verified or not user.tasker_security_verified:
            raise ValueError("Le chauffeur n'a pas terminé ses vérifications de sécurité")
        if not profile.is_active:
            raise ValueError("Le profil chauffeur est inactif")
        if not profile.vehicle_ready:
            raise ValueError("Le chauffeur n'est pas prêt pour recevoir des courses")
        if profile.verification_status not in {"approved", "verified"}:
            raise ValueError("Le profil chauffeur n'est pas encore vérifié")
        if profile.license_expires_at and profile.license_expires_at <= _utcnow():
            raise ValueError("Le permis du chauffeur a expiré")

    def _release_driver_from_ride(self, driver_user_id: str | None) -> None:
        if not driver_user_id:
            return
        profile = self.db.execute(select(VtcDriverProfile).where(VtcDriverProfile.user_id == driver_user_id)).scalars().one_or_none()
        if profile is None:
            return
        profile.current_ride_id = None
        profile.availability_status = "online" if profile.is_online else "offline"

    def _has_pending_offers(self, ride_id: str) -> bool:
        offer = self.db.execute(
            select(VtcRideDispatchOffer).where(
                VtcRideDispatchOffer.ride_id == ride_id,
                VtcRideDispatchOffer.status == "pending",
            )
        ).scalars().first()
        return offer is not None

    def _expire_other_stale_offers(self, ride_id: str) -> None:
        now = _utcnow()
        offers = self.db.execute(
            select(VtcRideDispatchOffer).where(
                VtcRideDispatchOffer.ride_id == ride_id,
                VtcRideDispatchOffer.status == "pending",
            )
        ).scalars().all()
        for offer in offers:
            if offer.expires_at and offer.expires_at < now:
                offer.status = "expired"
                offer.responded_at = now

    def _finalize_ride_amounts(self, ride: VtcRideRequest, *, final_fare: Decimal | None) -> None:
        amount = _to_decimal(final_fare or ride.quoted_fare or ride.estimated_fare, "0")
        ride.final_fare = amount
        platform_fee_rate = self._operator_platform_fee_rate(ride.operator_id)
        platform_fee_amount = (amount * platform_fee_rate).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        ride.platform_fee_amount = platform_fee_amount
        ride.driver_payout_amount = (amount - platform_fee_amount).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
        ride.payout_status = "pending"

    def _build_quote(
        self,
        *,
        operator: VtcFleetOperator | None,
        currency: str,
        pickup_latitude: float | None,
        pickup_longitude: float | None,
        destination_latitude: float | None,
        destination_longitude: float | None,
        estimated_distance_km: Decimal | None,
        estimated_duration_minutes: int | None,
        estimated_fare: Decimal | None,
        ride_type: str,
    ) -> dict[str, Decimal]:
        return self.pricing_service.quote_vtc_ride(
            operator=operator,
            currency=currency,
            ride_type=ride_type,
            pickup_latitude=pickup_latitude,
            pickup_longitude=pickup_longitude,
            destination_latitude=destination_latitude,
            destination_longitude=destination_longitude,
            estimated_distance_km=estimated_distance_km,
            estimated_duration_minutes=estimated_duration_minutes,
            estimated_fare=estimated_fare,
        )

    def _operator_platform_fee_rate(self, operator_id: str | None) -> Decimal:
        operator = self._load_operator(operator_id) if operator_id else None
        metadata = self._safe_json_loads(operator.metadata_json) if operator and operator.metadata_json else {}
        value = None
        if isinstance(metadata, dict):
            pricing = metadata.get("pricing")
            if isinstance(pricing, dict):
                value = pricing.get("platformFeeRate")
        return _to_decimal(value, "0.20").quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

    def _append_ride_event(
        self,
        *,
        ride: VtcRideRequest,
        event_type: str,
        actor_user_id: str | None,
        note: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            VtcRideEvent(
                ride_id=ride.id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                event_note=note,
                payload_json=json.dumps(payload) if payload is not None else None,
            )
        )

    def _ensure_wallets(self, user_id: str, country_code: str) -> None:
        currencies = {"USD", CountryRolloutService(self.db).resolve_local_currency(country_code, fallback="EUR")}
        for currency in currencies:
            self.db.add(Wallet(user_id=user_id, currency=currency, balance=Decimal("0")))

    def _load_driver_profile(self, user_id: str, *, for_update: bool = False) -> VtcDriverProfile:
        stmt = select(VtcDriverProfile).where(VtcDriverProfile.user_id == user_id)
        if for_update:
            stmt = stmt.with_for_update()
        profile = self.db.execute(stmt).scalars().one_or_none()
        if profile is None:
            raise ValueError("Profil chauffeur introuvable")
        return profile

    def _load_operator(self, operator_id: str | None) -> VtcFleetOperator | None:
        if not operator_id:
            return None
        operator = self.db.get(VtcFleetOperator, operator_id)
        if operator is None:
            raise ValueError("Opérateur introuvable")
        return operator

    def _require_ride_status(self, ride: VtcRideRequest, allowed: set[str]) -> None:
        if ride.status not in allowed:
            raise ValueError("Transition de course invalide")

    def _generate_ride_code(self) -> str:
        return f"VTC-{uuid.uuid4().hex[:8].upper()}"

    def _distance_km(
        self,
        lat1: float | None,
        lon1: float | None,
        lat2: float | None,
        lon2: float | None,
    ) -> Decimal | None:
        if None in {lat1, lon1, lat2, lon2}:
            return None
        radius = 6371.0
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        d_phi = math.radians(float(lat2) - float(lat1))
        d_lambda = math.radians(float(lon2) - float(lon1))
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return Decimal(str(radius * c)).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    def _safe_json_loads(self, payload: str | None) -> dict | list | None:
        if not payload:
            return None
        try:
            return json.loads(payload)
        except Exception:
            return None

    def _serialize_user(self, user: User) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "countryCode": user.country_code,
        }

    def _serialize_operator(self, item: VtcFleetOperator) -> dict:
        return {
            "id": item.id,
            "ownerUserId": item.owner_user_id,
            "serviceZoneId": item.service_zone_id,
            "publicName": item.public_name,
            "legalName": item.legal_name,
            "description": item.description,
            "countryCode": item.country_code,
            "cityName": item.city_name,
            "currency": item.currency,
            "phone": item.phone,
            "email": item.email,
            "isActive": bool(item.is_active),
            "acceptingRides": bool(item.accepting_rides),
            "launchStatus": item.launch_status,
            "metadata": self._safe_json_loads(item.metadata_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_driver_profile(self, item: VtcDriverProfile) -> dict:
        return {
            "id": item.id,
            "userId": item.user_id,
            "operatorId": item.operator_id,
            "currentRideId": item.current_ride_id,
            "licenseNumber": item.license_number,
            "licenseCountryCode": item.license_country_code,
            "licenseExpiresAt": item.license_expires_at.isoformat() if item.license_expires_at else None,
            "vehicleReady": bool(item.vehicle_ready),
            "isActive": bool(item.is_active),
            "isOnline": bool(item.is_online),
            "availabilityStatus": item.availability_status,
            "verificationStatus": item.verification_status,
            "currentLatitude": item.current_latitude,
            "currentLongitude": item.current_longitude,
            "lastLocationAt": item.last_location_at.isoformat() if item.last_location_at else None,
            "ridesCompletedCount": int(item.rides_completed_count or 0),
            "ridesCancelledCount": int(item.rides_cancelled_count or 0),
            "metadata": self._safe_json_loads(item.metadata_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_vehicle(self, item: VtcVehicle) -> dict:
        return {
            "id": item.id,
            "operatorId": item.operator_id,
            "driverUserId": item.driver_user_id,
            "make": item.make,
            "model": item.model,
            "color": item.color,
            "plateNumber": item.plate_number,
            "category": item.category,
            "seatsCount": item.seats_count,
            "isActive": bool(item.is_active),
            "verificationStatus": item.verification_status,
            "metadata": self._safe_json_loads(item.metadata_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_ride(self, item: VtcRideRequest) -> dict:
        return {
            "id": item.id,
            "rideCode": item.ride_code,
            "customerUserId": item.customer_user_id,
            "operatorId": item.operator_id,
            "driverUserId": item.driver_user_id,
            "linkedTaskId": item.linked_task_id,
            "cancelledByUserId": item.cancelled_by_user_id,
            "pickupAddress": item.pickup_address,
            "pickupLatitude": item.pickup_latitude,
            "pickupLongitude": item.pickup_longitude,
            "destinationAddress": item.destination_address,
            "destinationLatitude": item.destination_latitude,
            "destinationLongitude": item.destination_longitude,
            "scheduledAt": item.scheduled_at.isoformat() if item.scheduled_at else None,
            "requestedAt": item.requested_at.isoformat() if item.requested_at else None,
            "assignedAt": item.assigned_at.isoformat() if item.assigned_at else None,
            "acceptedAt": item.accepted_at.isoformat() if item.accepted_at else None,
            "driverEnRouteAt": item.driver_en_route_at.isoformat() if item.driver_en_route_at else None,
            "driverArrivedAt": item.driver_arrived_at.isoformat() if item.driver_arrived_at else None,
            "startedAt": item.started_at.isoformat() if item.started_at else None,
            "completedAt": item.completed_at.isoformat() if item.completed_at else None,
            "cancelledAt": item.cancelled_at.isoformat() if item.cancelled_at else None,
            "payoutCompletedAt": item.payout_completed_at.isoformat() if item.payout_completed_at else None,
            "driverOfferExpiresAt": item.driver_offer_expires_at.isoformat() if item.driver_offer_expires_at else None,
            "estimatedDistanceKm": str(item.estimated_distance_km) if item.estimated_distance_km is not None else None,
            "estimatedDurationMinutes": item.estimated_duration_minutes,
            "estimatedFare": str(item.estimated_fare) if item.estimated_fare is not None else None,
            "quotedFare": str(item.quoted_fare) if item.quoted_fare is not None else None,
            "finalFare": str(item.final_fare) if item.final_fare is not None else None,
            "baseFareAmount": str(item.base_fare_amount) if item.base_fare_amount is not None else None,
            "distanceFareAmount": str(item.distance_fare_amount) if item.distance_fare_amount is not None else None,
            "timeFareAmount": str(item.time_fare_amount) if item.time_fare_amount is not None else None,
            "surgeMultiplier": str(item.surge_multiplier) if item.surge_multiplier is not None else None,
            "platformFeeAmount": str(item.platform_fee_amount) if item.platform_fee_amount is not None else None,
            "driverPayoutAmount": str(item.driver_payout_amount) if item.driver_payout_amount is not None else None,
            "pricingBreakdown": self.pricing_service.serialize_quote(
                {
                    "moduleCode": "VTC",
                    "currency": item.currency,
                    "rideType": item.ride_type,
                    "estimatedDistanceKm": item.estimated_distance_km,
                    "estimatedDurationMinutes": item.estimated_duration_minutes,
                    "quotedFare": item.quoted_fare,
                    "finalFare": item.final_fare,
                    "baseFareAmount": item.base_fare_amount,
                    "distanceFareAmount": item.distance_fare_amount,
                    "timeFareAmount": item.time_fare_amount,
                    "surgeMultiplier": item.surge_multiplier,
                    "platformFeeAmount": item.platform_fee_amount,
                    "driverPayoutAmount": item.driver_payout_amount,
                }
            ),
            "currency": item.currency,
            "status": item.status,
            "dispatchStatus": item.dispatch_status,
            "payoutStatus": item.payout_status,
            "rideType": item.ride_type,
            "passengerName": item.passenger_name,
            "passengerPhone": item.passenger_phone,
            "customerNote": item.customer_note,
            "cancellationReason": item.cancellation_reason,
            "lastDriverLatitude": item.last_driver_latitude,
            "lastDriverLongitude": item.last_driver_longitude,
            "lastDriverHeading": item.last_driver_heading,
            "lastDriverLocationAt": item.last_driver_location_at.isoformat() if item.last_driver_location_at else None,
            "metadata": self._safe_json_loads(item.metadata_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_offer(self, item: VtcRideDispatchOffer) -> dict:
        return {
            "id": item.id,
            "rideId": item.ride_id,
            "driverUserId": item.driver_user_id,
            "operatorId": item.operator_id,
            "vehicleId": item.vehicle_id,
            "status": item.status,
            "distanceToPickupKm": str(item.distance_to_pickup_km) if item.distance_to_pickup_km is not None else None,
            "rankingScore": str(item.ranking_score) if item.ranking_score is not None else None,
            "offeredAt": item.offered_at.isoformat() if item.offered_at else None,
            "expiresAt": item.expires_at.isoformat() if item.expires_at else None,
            "respondedAt": item.responded_at.isoformat() if item.responded_at else None,
            "metadata": self._safe_json_loads(item.metadata_json),
        }

    def _serialize_event(self, item: VtcRideEvent) -> dict:
        return {
            "id": item.id,
            "rideId": item.ride_id,
            "actorUserId": item.actor_user_id,
            "eventType": item.event_type,
            "eventNote": item.event_note,
            "payload": self._safe_json_loads(item.payload_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }
