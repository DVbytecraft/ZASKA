import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MerchantPartner(Base):
    __tablename__ = "merchant_partners"

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
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    accepts_cash_on_delivery: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    accepting_orders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    launch_status: Mapped[str] = mapped_column(String(16), default="CONFIGURED", nullable=False, server_default="CONFIGURED")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MerchantStaffAssignment(Base):
    __tablename__ = "merchant_staff_assignments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_partners.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    staff_role: Mapped[str] = mapped_column(String(32), default="manager", nullable=False, server_default="manager")
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MerchantCatalog(Base):
    __tablename__ = "merchant_catalogs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_partners.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class MerchantCatalogItem(Base):
    __tablename__ = "merchant_catalog_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    catalog_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_catalogs.id"), index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8))
    sku: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    stock_quantity: Mapped[int | None] = mapped_column(nullable=True)
    track_inventory: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    is_available: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, server_default="true")
    is_sold_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    attributes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ShopOrder(Base):
    __tablename__ = "shop_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_partners.id"), index=True)
    customer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    linked_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    delivery_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    delivery_escrow_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("escrows.id"), nullable=True, index=True)
    merchandise_hold_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("shop_payment_holds.id"), nullable=True, index=True)
    beneficiary_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    beneficiary_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ordered_for_other: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, server_default="false")
    delivery_address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    country_code: Mapped[str | None] = mapped_column(String(2), nullable=True, index=True)
    city_name: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    subtotal_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    delivery_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), default=Decimal("0"), nullable=False, server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    fulfillment_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    dispatch_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending", index=True)
    payment_status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False, server_default="pending")
    source: Mapped[str] = mapped_column(String(24), default="shop", nullable=False, server_default="shop")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    customer_funded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    merchant_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ready_for_dispatch_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payout_completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ShopOrderItem(Base):
    __tablename__ = "shop_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("shop_orders.id"), index=True)
    catalog_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_catalog_items.id"), index=True)
    quantity: Mapped[int] = mapped_column(nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8))
    snapshot_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ShopPaymentHold(Base):
    __tablename__ = "shop_payment_holds"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("shop_orders.id"), index=True)
    payer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    beneficiary_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6))
    currency: Mapped[str] = mapped_column(String(8))
    status: Mapped[str] = mapped_column(String(24), default="funded", nullable=False, server_default="funded", index=True)
    funding_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    settlement_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ShopMerchantPayoutSnapshot(Base):
    __tablename__ = "shop_merchant_payout_snapshots"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    period_key: Mapped[str] = mapped_column(String(16), index=True)
    merchant_id: Mapped[str] = mapped_column(String(36), ForeignKey("merchant_partners.id"), index=True)
    currency: Mapped[str] = mapped_column(String(8), index=True)
    order_count: Mapped[int] = mapped_column(nullable=False, default=0, server_default="0")
    gross_goods_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    released_payout_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    refunded_goods_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    pending_goods_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    delivery_fee_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class ShopOrderEvent(Base):
    __tablename__ = "shop_order_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    shop_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("shop_orders.id"), index=True)
    actor_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    event_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
