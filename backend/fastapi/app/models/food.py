from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RestaurantPartner(Base):
    __tablename__ = "restaurant_partners"
    __table_args__ = (
        Index("ix_restaurant_partner_country_city", "country_code", "city_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    owner_user_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True, index=True)
    service_zone_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("service_zones.id"), nullable=True, index=True)
    public_name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    legal_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    city_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    address: Mapped[str | None] = mapped_column(String(512), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    accepts_cash_on_delivery: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    accepting_orders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_temporarily_closed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    prep_buffer_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    launch_status: Mapped[str] = mapped_column(String(24), nullable=False, default="CONFIGURED", server_default="CONFIGURED")
    opening_hours_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RestaurantStaffAssignment(Base):
    __tablename__ = "restaurant_staff_assignments"
    __table_args__ = (
        UniqueConstraint("restaurant_id", "user_id", name="uq_restaurant_staff_assignment"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    staff_role: Mapped[str] = mapped_column(String(32), nullable=False, default="manager", server_default="manager")
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantMenu(Base):
    __tablename__ = "restaurant_menus"
    __table_args__ = (
        Index("ix_restaurant_menu_restaurant_active", "restaurant_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RestaurantMenuItem(Base):
    __tablename__ = "restaurant_menu_items"
    __table_args__ = (
        Index("ix_restaurant_menu_item_menu_available", "menu_id", "is_available"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    menu_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menus.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    is_sold_out: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    track_inventory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    stock_quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")
    available_from_hour: Mapped[str | None] = mapped_column(String(5), nullable=True)
    available_to_hour: Mapped[str | None] = mapped_column(String(5), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FoodOrder(Base):
    __tablename__ = "food_orders"
    __table_args__ = (
        Index("ix_food_order_customer_status", "customer_user_id", "status"),
        Index("ix_food_order_restaurant_status", "restaurant_id", "status"),
        Index("ix_food_order_country_city", "country_code", "city_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    customer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    delivery_task_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("tasks.id"), nullable=True, index=True)
    meal_hold_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("food_payment_holds.id"), nullable=True, index=True)
    delivery_escrow_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("escrows.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending_restaurant", server_default="pending_restaurant")
    payment_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    dispatch_status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", server_default="pending")
    country_code: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    city_name: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    delivery_fee: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    total_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    restaurant_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    delivery_amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    ordered_for_other: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    beneficiary_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    beneficiary_phone: Mapped[str | None] = mapped_column(String(32), nullable=True)
    delivery_address: Mapped[str] = mapped_column(String(512), nullable=False)
    delivery_latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    delivery_longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_prep_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=20, server_default="20")
    restaurant_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class FoodOrderItem(Base):
    __tablename__ = "food_order_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    food_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("food_orders.id"), nullable=False, index=True)
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_items.id"), nullable=False, index=True)
    combo_offer_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("restaurant_combo_offers.id"), nullable=True, index=True)
    line_type: Mapped[str] = mapped_column(String(24), nullable=False, default="menu_item", server_default="menu_item")
    item_name: Mapped[str] = mapped_column(String(160), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    modifier_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    line_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class FoodPaymentHold(Base):
    __tablename__ = "food_payment_holds"
    __table_args__ = (
        Index("ix_food_payment_hold_order_status", "food_order_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    food_order_id: Mapped[str] = mapped_column(String(36), ForeignKey("food_orders.id"), nullable=False, index=True)
    payer_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    beneficiary_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False, index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="funded", server_default="funded")
    hold_type: Mapped[str] = mapped_column(String(32), nullable=False, default="restaurant_meal_payout", server_default="restaurant_meal_payout")
    funding_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    settlement_tx_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("transactions.id"), nullable=True, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class RestaurantPayoutSnapshot(Base):
    __tablename__ = "restaurant_payout_snapshots"
    __table_args__ = (
        UniqueConstraint("period_key", "restaurant_id", "currency", name="uq_restaurant_payout_snapshot_period_restaurant_currency"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    period_key: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    order_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    gross_meal_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    released_payout_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    refunded_meal_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    pending_meal_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    delivery_fee_total: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantSpecialClosure(Base):
    __tablename__ = "restaurant_special_closures"
    __table_args__ = (
        Index("ix_restaurant_special_closure_window", "restaurant_id", "starts_at", "ends_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantComboOffer(Base):
    __tablename__ = "restaurant_combo_offers"
    __table_args__ = (
        Index("ix_restaurant_combo_offer_restaurant_active", "restaurant_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    restaurant_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_partners.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    available_from_hour: Mapped[str | None] = mapped_column(String(5), nullable=True)
    available_to_hour: Mapped[str | None] = mapped_column(String(5), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantComboItem(Base):
    __tablename__ = "restaurant_combo_items"
    __table_args__ = (
        Index("ix_restaurant_combo_item_combo", "combo_offer_id", "menu_item_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    combo_offer_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_combo_offers.id"), nullable=False, index=True)
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_items.id"), nullable=False, index=True)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantMenuItemModifierGroup(Base):
    __tablename__ = "restaurant_menu_item_modifier_groups"
    __table_args__ = (
        Index("ix_restaurant_modifier_group_item_active", "menu_item_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    menu_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_items.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    min_select: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    max_select: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class RestaurantMenuItemModifierOption(Base):
    __tablename__ = "restaurant_menu_item_modifier_options"
    __table_args__ = (
        Index("ix_restaurant_modifier_option_group_active", "modifier_group_id", "is_active"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    modifier_group_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_item_modifier_groups.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    currency: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))


class FoodOrderItemModifierSelection(Base):
    __tablename__ = "food_order_item_modifier_selections"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    food_order_item_id: Mapped[str] = mapped_column(String(36), ForeignKey("food_order_items.id"), nullable=False, index=True)
    modifier_group_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_item_modifier_groups.id"), nullable=False, index=True)
    modifier_option_id: Mapped[str] = mapped_column(String(36), ForeignKey("restaurant_menu_item_modifier_options.id"), nullable=False, index=True)
    group_name: Mapped[str] = mapped_column(String(120), nullable=False)
    option_name: Mapped[str] = mapped_column(String(120), nullable=False)
    price_delta: Mapped[Decimal] = mapped_column(Numeric(20, 6), nullable=False, default=Decimal("0"), server_default="0")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
