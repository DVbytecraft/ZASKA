import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class VtcFleetOperator(Base):
    __tablename__ = "vtc_fleet_operators"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    service_zone_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("service_zones.id"), nullable=True, index=True)
    public_name: Mapped[str] = mapped_column(String(160), index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str] = mapped_column(String(2), index=True)
    city_name: Mapped[str] = mapped_column(String(128), index=True)
    currency: Mapped[str] = mapped_column(String(8))
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    accepting_rides: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    launch_status: Mapped[str] = mapped_column(String(16), default="CONFIGURED", nullable=False, server_default="CONFIGURED")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VtcDriverProfile(Base):
    __tablename__ = "vtc_driver_profiles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_fleet_operators.id"), nullable=True, index=True)
    current_ride_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_ride_requests.id"), nullable=True, index=True)
    license_number: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    license_country_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    license_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    vehicle_ready: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    availability_status: Mapped[str] = mapped_column(String(24), default="offline", nullable=False, server_default="offline", index=True)
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending")
    current_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    current_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rides_completed_count: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    rides_cancelled_count: Mapped[int] = mapped_column(default=0, nullable=False, server_default="0")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VtcVehicle(Base):
    __tablename__ = "vtc_vehicles"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    operator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_fleet_operators.id"), nullable=True, index=True)
    driver_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    make: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(64))
    color: Mapped[str | None] = mapped_column(String(32), nullable=True)
    plate_number: Mapped[str] = mapped_column(String(32), index=True)
    category: Mapped[str] = mapped_column(String(24), default="standard", nullable=False, server_default="standard")
    seats_count: Mapped[int] = mapped_column(nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    verification_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VtcRideRequest(Base):
    __tablename__ = "vtc_ride_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    customer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_fleet_operators.id"), nullable=True, index=True)
    driver_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    cancelled_by_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    ride_code: Mapped[str | None] = mapped_column(String(24), nullable=True, index=True)
    pickup_address: Mapped[str] = mapped_column(String(512))
    pickup_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    pickup_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_address: Mapped[str] = mapped_column(String(512))
    destination_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    destination_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    assigned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    driver_en_route_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    driver_arrived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payout_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    driver_offer_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    estimated_distance_km: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    estimated_duration_minutes: Mapped[int | None] = mapped_column(nullable=True)
    estimated_fare: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    quoted_fare: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    final_fare: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    base_fare_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    distance_fare_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    time_fare_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    surge_multiplier: Mapped[Decimal | None] = mapped_column(Numeric(8, 4), nullable=True)
    platform_fee_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    driver_payout_amount: Mapped[Decimal | None] = mapped_column(Numeric(20, 6), nullable=True)
    currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, server_default="draft", index=True)
    dispatch_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    payout_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    ride_type: Mapped[str] = mapped_column(String(24), default="standard", nullable=False, server_default="standard")
    passenger_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    passenger_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_driver_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_driver_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_driver_heading: Mapped[float | None] = mapped_column(Float, nullable=True)
    last_driver_location_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class VtcRideDispatchOffer(Base):
    __tablename__ = "vtc_ride_dispatch_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ride_id: Mapped[str] = mapped_column(String(36), ForeignKey("vtc_ride_requests.id"), index=True)
    driver_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    operator_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_fleet_operators.id"), nullable=True, index=True)
    vehicle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("vtc_vehicles.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    distance_to_pickup_km: Mapped[Decimal | None] = mapped_column(Numeric(12, 3), nullable=True)
    ranking_score: Mapped[Decimal | None] = mapped_column(Numeric(12, 6), nullable=True)
    offered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class VtcRideEvent(Base):
    __tablename__ = "vtc_ride_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    ride_id: Mapped[str] = mapped_column(String(36), ForeignKey("vtc_ride_requests.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
