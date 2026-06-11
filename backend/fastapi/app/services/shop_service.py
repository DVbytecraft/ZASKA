from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models.shop import (
    MerchantCatalog,
    MerchantCatalogItem,
    MerchantPartner,
    MerchantStaffAssignment,
    ShopMerchantPayoutSnapshot,
    ShopOrder,
    ShopOrderEvent,
    ShopOrderItem,
    ShopPaymentHold,
)
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow, Transaction, Wallet
from app.services.country_rollout_service import CountryRolloutService
from app.services.pricing_engine_service import PricingEngineService
from app.services.task_service import TaskService
from app.services.wallet_service import InsufficientFundsError, WalletService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class ShopService:
    def __init__(self, db: Session):
        self.db = db
        self.wallet_service = WalletService(db)
        self.task_service = TaskService(db)
        self.pricing_service = PricingEngineService(db)

    def create_merchant_user(
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
            id=_uuid(),
            email=email_norm,
            phone=phone.strip() if phone else None,
            first_name=first_name,
            last_name=last_name,
            full_name=f"{first_name} {last_name}".strip(),
            password_hash=get_password_hash(password),
            role="merchant",
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

    def create_merchant(
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
        address: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        phone: str | None = None,
        email: str | None = None,
        accepts_cash_on_delivery: bool = False,
        is_active: bool = True,
        accepting_orders: bool = True,
        launch_status: str = "CONFIGURED",
        metadata: dict | None = None,
    ) -> dict:
        item = MerchantPartner(
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
            address=address,
            latitude=latitude,
            longitude=longitude,
            accepts_cash_on_delivery=accepts_cash_on_delivery,
            is_active=is_active,
            accepting_orders=accepting_orders,
            launch_status=launch_status,
            metadata_json=json.dumps(metadata) if metadata is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_merchant(item)

    def list_merchants(
        self,
        *,
        country_code: str | None = None,
        city_name: str | None = None,
        active_only: bool = False,
        reference_latitude: float | None = None,
        reference_longitude: float | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        stmt = select(MerchantPartner).order_by(desc(MerchantPartner.created_at))
        if country_code:
            stmt = stmt.where(MerchantPartner.country_code == country_code.upper())
        if city_name:
            stmt = stmt.where(MerchantPartner.city_name.ilike(f"%{city_name.strip()}%"))
        if active_only:
            stmt = stmt.where(MerchantPartner.is_active.is_(True), MerchantPartner.accepting_orders.is_(True))
        rows = self.db.execute(stmt).scalars().all()
        payload = [self._serialize_merchant(row) for row in rows]
        for item in payload:
            item["distanceKm"] = self._distance_km(
                reference_latitude,
                reference_longitude,
                item.get("latitude"),
                item.get("longitude"),
            )
        payload.sort(
            key=lambda item: (
                item["distanceKm"] is None,
                item["distanceKm"] if item["distanceKm"] is not None else 999999,
                str(item.get("publicName") or "").lower(),
            )
        )
        return payload[:limit] if limit else payload

    def add_staff(
        self,
        *,
        merchant_id: str,
        user_id: str,
        staff_role: str = "manager",
        is_primary: bool = False,
    ) -> dict:
        if self.db.get(MerchantPartner, merchant_id) is None:
            raise ValueError("Marchand introuvable")
        if self.db.get(User, user_id) is None:
            raise ValueError("Utilisateur introuvable")
        existing = self.db.execute(
            select(MerchantStaffAssignment).where(
                MerchantStaffAssignment.merchant_id == merchant_id,
                MerchantStaffAssignment.user_id == user_id,
            )
        ).scalars().one_or_none()
        if existing is not None:
            raise ValueError("Cet utilisateur est déjà rattaché à ce marchand")
        item = MerchantStaffAssignment(
            merchant_id=merchant_id,
            user_id=user_id,
            staff_role=staff_role,
            is_primary=is_primary,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_staff(item)

    def create_catalog(
        self,
        *,
        merchant_id: str,
        name: str,
        description: str | None = None,
        is_active: bool = True,
        is_default: bool = False,
    ) -> dict:
        if self.db.get(MerchantPartner, merchant_id) is None:
            raise ValueError("Marchand introuvable")
        item = MerchantCatalog(
            merchant_id=merchant_id,
            name=name,
            description=description,
            is_active=is_active,
            is_default=is_default,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_catalog(item)

    def list_catalogs(self, *, merchant_id: str | None = None) -> list[dict]:
        stmt = select(MerchantCatalog).order_by(desc(MerchantCatalog.created_at))
        if merchant_id:
            stmt = stmt.where(MerchantCatalog.merchant_id == merchant_id)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_catalog(row) for row in rows]

    def create_catalog_item(
        self,
        *,
        catalog_id: str,
        name: str,
        price: Decimal,
        currency: str,
        description: str | None = None,
        category: str | None = None,
        sku: str | None = None,
        stock_quantity: int | None = None,
        track_inventory: bool = False,
        is_available: bool = True,
        is_sold_out: bool = False,
        image_url: str | None = None,
        attributes: dict | None = None,
    ) -> dict:
        if self.db.get(MerchantCatalog, catalog_id) is None:
            raise ValueError("Catalogue introuvable")
        item = MerchantCatalogItem(
            catalog_id=catalog_id,
            name=name,
            description=description,
            category=category,
            price=price,
            currency=currency.upper(),
            sku=sku,
            stock_quantity=stock_quantity,
            track_inventory=track_inventory,
            is_available=is_available,
            is_sold_out=is_sold_out,
            image_url=image_url,
            attributes_json=json.dumps(attributes) if attributes is not None else None,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._serialize_item(item)

    def list_catalog_items(
        self,
        *,
        catalog_id: str | None = None,
        merchant_id: str | None = None,
        category: str | None = None,
        active_only: bool = False,
    ) -> list[dict]:
        stmt = select(MerchantCatalogItem).order_by(desc(MerchantCatalogItem.created_at))
        if catalog_id:
            stmt = stmt.where(MerchantCatalogItem.catalog_id == catalog_id)
        rows = self.db.execute(stmt).scalars().all()
        if merchant_id:
            catalog_ids = {item["id"] for item in self.list_catalogs(merchant_id=merchant_id)}
            rows = [row for row in rows if row.catalog_id in catalog_ids]
        if category:
            rows = [row for row in rows if row.category == category]
        if active_only:
            rows = [row for row in rows if row.is_available and not row.is_sold_out]
        return [self._serialize_item(row) for row in rows]

    def create_order(
        self,
        *,
        merchant_id: str,
        customer_user_id: str,
        items: list[dict],
        beneficiary_name: str | None = None,
        beneficiary_phone: str | None = None,
        ordered_for_other: bool = False,
        delivery_address: str | None = None,
        delivery_latitude: float | None = None,
        delivery_longitude: float | None = None,
        delivery_amount: Decimal | None = None,
        notes: str | None = None,
        customer_note: str | None = None,
        metadata: dict | None = None,
    ) -> dict:
        merchant = self.db.get(MerchantPartner, merchant_id)
        if merchant is None:
            raise ValueError("Marchand introuvable")
        customer = self.db.get(User, customer_user_id)
        if customer is None:
            raise ValueError("Client introuvable")
        if not merchant.is_active or not merchant.accepting_orders:
            raise ValueError("Ce marchand n'accepte pas de commandes actuellement")
        if delivery_amount and delivery_amount > Decimal("0") and not delivery_address:
            raise ValueError("Adresse de livraison requise pour une commande avec livraison")
        pricing_breakdown = self.pricing_service.quote_shop_delivery(
            merchant=merchant,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            requested_delivery_fee=delivery_amount,
        )

        order_items_payload: list[tuple[MerchantCatalogItem, int]] = []
        subtotal = Decimal("0")
        currency = merchant.currency.upper()
        for raw_item in items:
            catalog_item = self.db.get(MerchantCatalogItem, raw_item["catalog_item_id"])
            if catalog_item is None:
                raise ValueError("Article introuvable")
            quantity = int(raw_item["quantity"])
            if quantity <= 0:
                raise ValueError("Quantité invalide")
            if catalog_item.currency.upper() != currency:
                raise ValueError("Tous les articles d'une commande doivent partager la même devise")
            if not catalog_item.is_available or catalog_item.is_sold_out:
                raise ValueError(f"L'article {catalog_item.name} n'est pas disponible")
            if catalog_item.track_inventory and catalog_item.stock_quantity is not None and catalog_item.stock_quantity < quantity:
                raise ValueError(f"Stock insuffisant pour l'article {catalog_item.name}")
            order_items_payload.append((catalog_item, quantity))
            subtotal += Decimal(str(catalog_item.price)) * quantity

        delivery = Decimal(str(pricing_breakdown["finalFee"]))
        total = subtotal + delivery
        order = ShopOrder(
            merchant_id=merchant_id,
            customer_user_id=customer_user_id,
            beneficiary_name=beneficiary_name,
            beneficiary_phone=beneficiary_phone,
            ordered_for_other=ordered_for_other,
            delivery_address=delivery_address,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            country_code=merchant.country_code,
            city_name=merchant.city_name,
            subtotal_amount=subtotal,
            delivery_amount=delivery,
            total_amount=total,
            currency=currency,
            notes=notes,
            customer_note=customer_note,
            metadata_json=json.dumps(
                self._merge_metadata(
                    json.dumps(metadata) if metadata is not None else None,
                    {"pricingBreakdown": self.pricing_service.serialize_quote(pricing_breakdown)},
                )
            ),
        )
        self.db.add(order)
        self.db.flush()
        self._append_order_event(
            order=order,
            event_type="order_created",
            actor_user_id=customer_user_id,
            note="Commande créée",
        )

        for catalog_item, quantity in order_items_payload:
            if catalog_item.track_inventory and catalog_item.stock_quantity is not None:
                catalog_item.stock_quantity -= quantity
                if catalog_item.stock_quantity <= 0:
                    catalog_item.is_sold_out = True
            line_total = Decimal(str(catalog_item.price)) * quantity
            self.db.add(
                ShopOrderItem(
                    shop_order_id=order.id,
                    catalog_item_id=catalog_item.id,
                    quantity=quantity,
                    unit_price=catalog_item.price,
                    line_total=line_total,
                    currency=currency,
                    snapshot_json=json.dumps(
                        {
                            "name": catalog_item.name,
                            "sku": catalog_item.sku,
                            "category": catalog_item.category,
                            "imageUrl": catalog_item.image_url,
                        }
                    ),
                )
            )

        self.db.commit()
        self.db.refresh(order)
        return self.get_order_detail(order.id)

    def quote_delivery(
        self,
        *,
        merchant_id: str,
        delivery_latitude: float | None,
        delivery_longitude: float | None,
        requested_delivery_fee: Decimal | None = None,
    ) -> dict[str, object]:
        merchant = self.db.get(MerchantPartner, merchant_id)
        if merchant is None:
            raise ValueError("Marchand introuvable")
        quote = self.pricing_service.quote_shop_delivery(
            merchant=merchant,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            requested_delivery_fee=requested_delivery_fee,
        )
        return self.pricing_service.serialize_quote(quote)

    def fund_order(self, *, order_id: str, customer_user_id: str) -> dict:
        order = self.db.execute(
            select(ShopOrder).where(ShopOrder.id == order_id).with_for_update()
        ).scalars().one_or_none()
        if order is None or order.customer_user_id != customer_user_id:
            raise ValueError("Commande introuvable")
        merchant = self.db.get(MerchantPartner, order.merchant_id)
        if merchant is None:
            raise ValueError("Marchand introuvable")
        if order.payment_status in {"funded", "completed"}:
            return self.get_order_detail(order.id)
        if order.merchandise_hold_id is None:
            hold = self._create_merchandise_hold_without_commit(order=order, beneficiary_user_id=merchant.owner_user_id or merchant.owner_user_id)
            order.merchandise_hold_id = hold.id
        if order.delivery_amount > Decimal("0") and order.delivery_task_id is None:
            if order.delivery_latitude is None or order.delivery_longitude is None:
                raise ValueError("Les coordonnées de livraison sont requises pour la livraison shop")
            task = self.task_service.create_task(
                {
                    "title": f"Livraison articles · {merchant.public_name}",
                    "description": f"Livraison d'articles pour la commande shop {order.id} vers {order.delivery_address}.",
                    "price": order.delivery_amount,
                    "currency": order.currency,
                    "latitude": order.delivery_latitude,
                    "longitude": order.delivery_longitude,
                    "address": order.delivery_address,
                    "status": "OPEN",
                    "created_by": customer_user_id,
                    "service_category": "SHOP_DELIVERY",
                    "mode": "fast",
                    "city": order.city_name,
                    "country": order.country_code,
                },
                commit=False,
            )
            order.delivery_task_id = task.id
            order.linked_task_id = task.id
            escrow = self._create_delivery_escrow_without_commit(
                task_id=task.id,
                payer_id=customer_user_id,
                amount=order.delivery_amount,
                currency=order.currency,
            )
            order.delivery_escrow_id = escrow.id
            order.dispatch_status = "created"
        else:
            order.dispatch_status = "not_required"
        order.payment_status = "funded"
        order.status = "merchant_pending_confirmation"
        order.fulfillment_status = "pending"
        order.customer_funded_at = _utcnow()
        self._append_order_event(
            order=order,
            event_type="order_funded",
            actor_user_id=customer_user_id,
            note="Commande financée",
        )
        self.db.commit()
        return self.get_order_detail(order.id)

    def list_orders(
        self,
        *,
        customer_user_id: str | None = None,
        merchant_id: str | None = None,
        status: str | None = None,
    ) -> list[dict]:
        stmt = select(ShopOrder).order_by(desc(ShopOrder.created_at))
        if customer_user_id:
            stmt = stmt.where(ShopOrder.customer_user_id == customer_user_id)
        if merchant_id:
            stmt = stmt.where(ShopOrder.merchant_id == merchant_id)
        if status:
            stmt = stmt.where(ShopOrder.status == status)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_order(row) for row in rows]

    def list_merchant_orders(self, actor_user_id: str, *, status: str | None = None) -> list[dict]:
        merchant_ids = self._merchant_ids_for_user(actor_user_id)
        if not merchant_ids:
            return []
        stmt = select(ShopOrder).where(ShopOrder.merchant_id.in_(merchant_ids)).order_by(desc(ShopOrder.created_at))
        if status:
            stmt = stmt.where(ShopOrder.status == status)
        rows = self.db.execute(stmt).scalars().all()
        return [self._serialize_order(row) for row in rows]

    def get_order_detail(self, order_id: str) -> dict:
        order = self.db.get(ShopOrder, order_id)
        if order is None:
            raise ValueError("Commande introuvable")
        items = self.db.execute(
            select(ShopOrderItem).where(ShopOrderItem.shop_order_id == order_id)
        ).scalars().all()
        events = self.db.execute(
            select(ShopOrderEvent).where(ShopOrderEvent.shop_order_id == order_id).order_by(ShopOrderEvent.created_at.asc())
        ).scalars().all()
        payload = self._serialize_order(order)
        payload["items"] = [self._serialize_order_item(item) for item in items]
        payload["events"] = [self._serialize_order_event(item) for item in events]
        return payload

    def update_merchant_order_status(
        self,
        *,
        actor_user_id: str,
        order_id: str,
        status: str,
        note: str | None = None,
    ) -> dict:
        order = self.db.execute(select(ShopOrder).where(ShopOrder.id == order_id).with_for_update()).scalars().one_or_none()
        if order is None:
            raise ValueError("Commande introuvable")
        if order.merchant_id not in self._merchant_ids_for_user(actor_user_id):
            raise ValueError("Accès marchand refusé")
        normalized = status.strip().lower()
        if normalized == "accepted":
            if order.payment_status not in {"funded", "completed"}:
                raise ValueError("La commande doit être financée avant confirmation")
            order.status = "merchant_confirmed"
            order.fulfillment_status = "accepted"
            order.merchant_confirmed_at = _utcnow()
            self._append_order_event(order=order, event_type="merchant_confirmed", actor_user_id=actor_user_id, note=note or "Commande confirmée par le marchand")
        elif normalized == "preparing":
            order.status = "preparing"
            order.fulfillment_status = "preparing"
            self._append_order_event(order=order, event_type="merchant_preparing", actor_user_id=actor_user_id, note=note or "Préparation en cours")
        elif normalized in {"ready", "ready_for_dispatch"}:
            order.status = "ready_for_dispatch"
            order.fulfillment_status = "ready"
            order.ready_for_dispatch_at = _utcnow()
            if order.delivery_task_id:
                order.dispatch_status = "awaiting_tasker"
            else:
                order.dispatch_status = "not_required"
            self._append_order_event(order=order, event_type="merchant_ready", actor_user_id=actor_user_id, note=note or "Commande prête")
        elif normalized == "delivered":
            if order.delivery_task_id:
                raise ValueError("Une commande avec livraison doit être finalisée par la tâche de livraison")
            self._complete_order_without_delivery(order=order, actor_user_id=actor_user_id, note=note)
        elif normalized == "cancelled":
            self._cancel_order_without_commit(order=order, actor_user_id=actor_user_id, reason=note or "Commande annulée par le marchand")
        else:
            raise ValueError("Statut marchand inconnu")
        self.db.commit()
        return self.get_order_detail(order.id)

    def sync_delivery_assignment(self, *, task_id: str, tasker_id: str) -> ShopOrder:
        order = self.db.execute(
            select(ShopOrder).where(ShopOrder.delivery_task_id == task_id).with_for_update()
        ).scalars().one_or_none()
        if order is None:
            raise ValueError("Commande shop liée à cette livraison introuvable")
        order.dispatch_status = "assigned"
        if order.status == "ready_for_dispatch":
            order.status = "out_for_delivery"
        self._append_order_event(
            order=order,
            event_type="delivery_task_assigned",
            actor_user_id=tasker_id,
            note="Livreur assigné à la commande",
            payload={"taskId": task_id, "taskerId": tasker_id},
        )
        self.db.flush()
        return order

    def finalize_order_from_delivery_task(self, *, task_id: str, commit: bool = True) -> ShopOrder:
        order = self.db.execute(
            select(ShopOrder).where(ShopOrder.delivery_task_id == task_id).with_for_update()
        ).scalars().one_or_none()
        if order is None:
            raise ValueError("Commande shop liée à cette livraison introuvable")
        if order.merchandise_hold_id:
            hold = self.db.get(ShopPaymentHold, order.merchandise_hold_id)
            if hold and hold.status == "funded":
                self._release_merchandise_hold_without_commit(hold)
        order.status = "delivered"
        order.fulfillment_status = "completed"
        order.dispatch_status = "completed"
        order.payment_status = "completed"
        order.delivered_at = _utcnow()
        order.payout_completed_at = order.delivered_at
        self._append_order_event(
            order=order,
            event_type="delivery_completed",
            actor_user_id=None,
            note="Commande livrée via tâche de livraison",
            payload={"taskId": task_id},
        )
        if commit:
            self.db.commit()
            self.db.refresh(order)
        else:
            self.db.flush()
        return order

    def build_merchant_payout_snapshots(
        self,
        *,
        period_key: str | None = None,
        merchant_id: str | None = None,
    ) -> list[dict[str, object]]:
        target_period = period_key or _utcnow().strftime("%Y-%m")
        rows = self.db.execute(
            select(ShopOrder, MerchantPartner, ShopPaymentHold)
            .join(MerchantPartner, MerchantPartner.id == ShopOrder.merchant_id)
            .join(ShopPaymentHold, ShopPaymentHold.id == ShopOrder.merchandise_hold_id, isouter=True)
            .order_by(ShopOrder.created_at.asc())
        ).all()
        aggregates: dict[tuple[str, str], dict[str, object]] = {}
        for order, merchant, hold in rows:
            created_at = order.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at.strftime("%Y-%m") != target_period:
                continue
            if merchant_id and merchant.id != merchant_id:
                continue
            key = (merchant.id, order.currency)
            bucket = aggregates.setdefault(
                key,
                {
                    "merchant": merchant,
                    "currency": order.currency,
                    "order_count": 0,
                    "gross_goods_total": Decimal("0"),
                    "released_payout_total": Decimal("0"),
                    "refunded_goods_total": Decimal("0"),
                    "pending_goods_total": Decimal("0"),
                    "delivery_fee_total": Decimal("0"),
                },
            )
            bucket["order_count"] += 1
            bucket["gross_goods_total"] += Decimal(str(order.subtotal_amount))
            bucket["delivery_fee_total"] += Decimal(str(order.delivery_amount))
            if hold is None:
                bucket["pending_goods_total"] += Decimal(str(order.subtotal_amount))
            elif hold.status == "released":
                bucket["released_payout_total"] += Decimal(str(hold.amount))
            elif hold.status == "refunded":
                bucket["refunded_goods_total"] += Decimal(str(hold.amount))
            else:
                bucket["pending_goods_total"] += Decimal(str(hold.amount))
        payloads: list[dict[str, object]] = []
        for (current_merchant_id, current_currency), bucket in aggregates.items():
            row = self.db.execute(
                select(ShopMerchantPayoutSnapshot).where(
                    ShopMerchantPayoutSnapshot.period_key == target_period,
                    ShopMerchantPayoutSnapshot.merchant_id == current_merchant_id,
                    ShopMerchantPayoutSnapshot.currency == current_currency,
                )
            ).scalars().one_or_none()
            metadata_json = json.dumps(
                {
                    "merchant_name": bucket["merchant"].public_name,
                    "generated_at": _utcnow().isoformat(),
                }
            )
            if row is None:
                row = ShopMerchantPayoutSnapshot(
                    id=_uuid(),
                    period_key=target_period,
                    merchant_id=current_merchant_id,
                    currency=current_currency,
                    order_count=int(bucket["order_count"]),
                    gross_goods_total=bucket["gross_goods_total"],
                    released_payout_total=bucket["released_payout_total"],
                    refunded_goods_total=bucket["refunded_goods_total"],
                    pending_goods_total=bucket["pending_goods_total"],
                    delivery_fee_total=bucket["delivery_fee_total"],
                    metadata_json=metadata_json,
                )
                self.db.add(row)
            else:
                row.order_count = int(bucket["order_count"])
                row.gross_goods_total = bucket["gross_goods_total"]
                row.released_payout_total = bucket["released_payout_total"]
                row.refunded_goods_total = bucket["refunded_goods_total"]
                row.pending_goods_total = bucket["pending_goods_total"]
                row.delivery_fee_total = bucket["delivery_fee_total"]
                row.metadata_json = metadata_json
            payloads.append(self._serialize_merchant_payout_snapshot(row, bucket["merchant"]))
        self.db.commit()
        return payloads

    def list_merchant_payout_snapshots(
        self,
        *,
        period_key: str | None = None,
        merchant_id: str | None = None,
        currency: str | None = None,
        actor_user_id: str | None = None,
    ) -> list[dict[str, object]]:
        stmt = (
            select(ShopMerchantPayoutSnapshot, MerchantPartner)
            .join(MerchantPartner, MerchantPartner.id == ShopMerchantPayoutSnapshot.merchant_id)
            .order_by(ShopMerchantPayoutSnapshot.period_key.desc(), MerchantPartner.public_name.asc())
        )
        if period_key:
            stmt = stmt.where(ShopMerchantPayoutSnapshot.period_key == period_key)
        if merchant_id:
            stmt = stmt.where(ShopMerchantPayoutSnapshot.merchant_id == merchant_id)
        if currency:
            stmt = stmt.where(ShopMerchantPayoutSnapshot.currency == currency.upper())
        if actor_user_id:
            merchant_ids = set(self._merchant_ids_for_user(actor_user_id))
            if merchant_ids:
                stmt = stmt.where(ShopMerchantPayoutSnapshot.merchant_id.in_(merchant_ids))
            else:
                return []
        rows = self.db.execute(stmt).all()
        return [self._serialize_merchant_payout_snapshot(snapshot, merchant) for snapshot, merchant in rows]

    def get_merchant_dashboard(self, user_id: str) -> dict:
        owned = self.db.execute(select(MerchantPartner).where(MerchantPartner.owner_user_id == user_id)).scalars().all()
        staff_assignments = self.db.execute(
            select(MerchantStaffAssignment).where(
                MerchantStaffAssignment.user_id == user_id,
                MerchantStaffAssignment.is_active.is_(True),
            )
        ).scalars().all()
        merchant_ids = {row.id for row in owned} | {row.merchant_id for row in staff_assignments}
        merchants = [self._serialize_merchant(self.db.get(MerchantPartner, merchant_id)) for merchant_id in merchant_ids if self.db.get(MerchantPartner, merchant_id)]
        catalogs = []
        orders = []
        for merchant_id in merchant_ids:
            catalogs.extend(self.list_catalogs(merchant_id=merchant_id))
            orders.extend(self.list_orders(merchant_id=merchant_id))
        return {
            "merchants": merchants,
            "catalogs": catalogs,
            "orders": orders,
            "staffAssignments": [self._serialize_staff(row) for row in staff_assignments],
            "payoutSnapshots": self.list_merchant_payout_snapshots(actor_user_id=user_id),
        }

    def _create_merchandise_hold_without_commit(self, *, order: ShopOrder, beneficiary_user_id: str | None) -> ShopPaymentHold:
        existing = self.db.execute(
            select(ShopPaymentHold).where(ShopPaymentHold.shop_order_id == order.id).with_for_update()
        ).scalars().one_or_none()
        if existing is not None:
            return existing
        if not beneficiary_user_id:
            raise ValueError("Aucun bénéficiaire marchand défini pour le règlement")
        wallet = self.wallet_service._get_or_create_wallet(order.customer_user_id, order.currency, for_update=True)
        if wallet.balance < order.subtotal_amount:
            raise InsufficientFundsError(f"Solde insuffisant : {wallet.balance} {order.currency} < {order.subtotal_amount} {order.currency}")
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="debit",
            amount=order.subtotal_amount,
            status="completed",
            reference=f"shop_goods_hold:{order.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "shop_goods_hold",
                    "shop_order_id": order.id,
                    "merchant_id": order.merchant_id,
                }
            ),
        )
        wallet.balance -= order.subtotal_amount
        self.db.add(tx)
        self.db.flush()
        hold = ShopPaymentHold(
            id=_uuid(),
            shop_order_id=order.id,
            payer_user_id=order.customer_user_id,
            beneficiary_user_id=beneficiary_user_id,
            amount=order.subtotal_amount,
            currency=order.currency,
            status="funded",
            funding_tx_id=tx.id,
            metadata_json=json.dumps({"merchant_id": order.merchant_id}),
        )
        self.db.add(hold)
        self.db.flush()
        return hold

    def _create_delivery_escrow_without_commit(
        self,
        *,
        task_id: str,
        payer_id: str,
        amount: Decimal,
        currency: str,
    ) -> Escrow:
        existing = self.wallet_service.get_escrow_by_task(task_id)
        if existing is not None:
            return existing
        wallet = self.wallet_service._get_or_create_wallet(payer_id, currency, for_update=True)
        if wallet.balance < amount:
            raise InsufficientFundsError(f"Solde insuffisant : {wallet.balance} {currency} < {amount} {currency}")
        escrow_id = _uuid()
        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="debit",
            amount=amount,
            status="completed",
            reference=f"shop_delivery_escrow_fund:{task_id}",
            provider="internal",
            metadata_json=json.dumps({"type": "shop_delivery_escrow_fund", "task_id": task_id}),
        )
        wallet.balance -= amount
        self.db.add(tx)
        self.db.flush()
        escrow = Escrow(
            id=escrow_id,
            task_id=task_id,
            payer_id=payer_id,
            payee_id=None,
            amount=amount,
            currency=currency,
            status="funded",
            funding_tx_id=tx.id,
        )
        self.db.add(escrow)
        self.db.flush()
        return escrow

    def _release_merchandise_hold_without_commit(self, hold: ShopPaymentHold) -> ShopPaymentHold:
        if hold.status != "funded":
            return hold
        beneficiary_wallet = self.wallet_service._get_or_create_wallet(hold.beneficiary_user_id, hold.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=beneficiary_wallet.id,
            type="credit",
            amount=hold.amount,
            status="completed",
            reference=f"shop_goods_release:{hold.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "shop_goods_release",
                    "shop_order_id": hold.shop_order_id,
                    "hold_id": hold.id,
                }
            ),
        )
        beneficiary_wallet.balance += hold.amount
        self.db.add(tx)
        self.db.flush()
        hold.settlement_tx_id = tx.id
        hold.status = "released"
        hold.updated_at = _utcnow()
        self.db.flush()
        return hold

    def _refund_merchandise_hold_without_commit(self, hold: ShopPaymentHold) -> ShopPaymentHold:
        if hold.status != "funded":
            return hold
        payer_wallet = self.wallet_service._get_or_create_wallet(hold.payer_user_id, hold.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=payer_wallet.id,
            type="credit",
            amount=hold.amount,
            status="completed",
            reference=f"shop_goods_refund:{hold.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "shop_goods_refund",
                    "shop_order_id": hold.shop_order_id,
                    "hold_id": hold.id,
                }
            ),
        )
        payer_wallet.balance += hold.amount
        self.db.add(tx)
        self.db.flush()
        hold.settlement_tx_id = tx.id
        hold.status = "refunded"
        hold.updated_at = _utcnow()
        self.db.flush()
        return hold

    def _refund_order_funding_without_commit(self, order: ShopOrder) -> None:
        if order.merchandise_hold_id:
            hold = self.db.get(ShopPaymentHold, order.merchandise_hold_id)
            if hold and hold.status == "funded":
                self._refund_merchandise_hold_without_commit(hold)
        if order.delivery_escrow_id:
            escrow = self.db.execute(
                select(Escrow).where(Escrow.id == order.delivery_escrow_id).with_for_update()
            ).scalars().one_or_none()
            if escrow and escrow.status in {"funded", "hold"}:
                payer_wallet = self.wallet_service._get_or_create_wallet(escrow.payer_id, escrow.currency, for_update=True)
                tx = Transaction(
                    id=_uuid(),
                    wallet_id=payer_wallet.id,
                    type="credit",
                    amount=escrow.amount,
                    status="completed",
                    reference=f"shop_delivery_refund:{escrow.id}",
                    provider="internal",
                    metadata_json=json.dumps(
                        {
                            "type": "shop_delivery_refund",
                            "shop_order_id": order.id,
                            "escrow_id": escrow.id,
                        }
                    ),
                )
                payer_wallet.balance += escrow.amount
                self.db.add(tx)
                self.db.flush()
                escrow.refund_tx_id = tx.id
                escrow.status = "refunded"
                self.db.flush()

    def _restore_inventory_without_commit(self, order: ShopOrder) -> None:
        items = self.db.execute(select(ShopOrderItem).where(ShopOrderItem.shop_order_id == order.id)).scalars().all()
        for line in items:
            catalog_item = self.db.get(MerchantCatalogItem, line.catalog_item_id)
            if catalog_item and catalog_item.track_inventory:
                catalog_item.stock_quantity = int(catalog_item.stock_quantity or 0) + int(line.quantity)
                catalog_item.is_sold_out = False

    def _cancel_order_without_commit(self, *, order: ShopOrder, actor_user_id: str | None, reason: str) -> None:
        if order.status == "cancelled":
            return
        self._refund_order_funding_without_commit(order)
        self._restore_inventory_without_commit(order)
        order.status = "cancelled"
        order.fulfillment_status = "cancelled"
        order.dispatch_status = "cancelled"
        order.payment_status = "refunded" if order.payment_status in {"funded", "completed"} else order.payment_status
        order.cancelled_at = _utcnow()
        order.cancellation_reason = reason
        self._append_order_event(order=order, event_type="order_cancelled", actor_user_id=actor_user_id, note=reason)

    def _complete_order_without_delivery(self, *, order: ShopOrder, actor_user_id: str | None, note: str | None) -> None:
        if order.merchandise_hold_id:
            hold = self.db.get(ShopPaymentHold, order.merchandise_hold_id)
            if hold and hold.status == "funded":
                self._release_merchandise_hold_without_commit(hold)
        order.status = "delivered"
        order.fulfillment_status = "completed"
        order.dispatch_status = "not_required"
        order.payment_status = "completed"
        order.delivered_at = _utcnow()
        order.payout_completed_at = order.delivered_at
        self._append_order_event(order=order, event_type="order_completed_without_delivery", actor_user_id=actor_user_id, note=note or "Commande remise sans livraison")

    def _append_order_event(
        self,
        *,
        order: ShopOrder,
        event_type: str,
        actor_user_id: str | None,
        note: str | None = None,
        payload: dict | None = None,
    ) -> None:
        self.db.add(
            ShopOrderEvent(
                id=_uuid(),
                shop_order_id=order.id,
                actor_user_id=actor_user_id,
                event_type=event_type,
                event_note=note,
                payload_json=json.dumps(payload) if payload is not None else None,
            )
        )

    def _merchant_ids_for_user(self, user_id: str) -> list[str]:
        owned = self.db.execute(select(MerchantPartner.id).where(MerchantPartner.owner_user_id == user_id)).scalars().all()
        assigned = self.db.execute(
            select(MerchantStaffAssignment.merchant_id).where(
                MerchantStaffAssignment.user_id == user_id,
                MerchantStaffAssignment.is_active.is_(True),
            )
        ).scalars().all()
        return list({*owned, *assigned})

    def _ensure_wallets(self, user_id: str, country_code: str) -> None:
        currencies = {"USD", CountryRolloutService(self.db).resolve_local_currency(country_code, fallback="EUR")}
        for currency in currencies:
            self.db.add(Wallet(user_id=user_id, currency=currency, balance=Decimal("0")))

    @staticmethod
    def _distance_km(lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None) -> float | None:
        if None in {lat1, lon1, lat2, lon2}:
            return None
        from math import atan2, cos, radians, sin, sqrt

        earth_radius_km = 6371.0
        dlat = radians(float(lat2) - float(lat1))
        dlon = radians(float(lon2) - float(lon1))
        a = (
            sin(dlat / 2) ** 2
            + cos(radians(float(lat1))) * cos(radians(float(lat2))) * sin(dlon / 2) ** 2
        )
        return earth_radius_km * 2 * atan2(sqrt(a), sqrt(1 - a))

    def _safe_json_loads(self, payload: str | None):
        if not payload:
            return None
        try:
            return json.loads(payload)
        except Exception:
            return None

    def _merge_metadata(self, existing_raw: str | None, extra: dict[str, object]) -> dict[str, object]:
        if not existing_raw:
            return dict(extra)
        try:
            payload = json.loads(existing_raw)
            if isinstance(payload, dict):
                payload.update(extra)
                return payload
        except Exception:
            pass
        return dict(extra)

    def _serialize_user(self, user: User) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "role": user.role,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "countryCode": user.country_code,
        }

    def _serialize_merchant(self, item: MerchantPartner) -> dict:
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
            "address": item.address,
            "latitude": item.latitude,
            "longitude": item.longitude,
            "acceptsCashOnDelivery": bool(item.accepts_cash_on_delivery),
            "isActive": bool(item.is_active),
            "acceptingOrders": bool(item.accepting_orders),
            "launchStatus": item.launch_status,
            "metadata": self._safe_json_loads(item.metadata_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_staff(self, item: MerchantStaffAssignment) -> dict:
        return {
            "id": item.id,
            "merchantId": item.merchant_id,
            "userId": item.user_id,
            "staffRole": item.staff_role,
            "isPrimary": bool(item.is_primary),
            "isActive": bool(item.is_active),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_catalog(self, item: MerchantCatalog) -> dict:
        return {
            "id": item.id,
            "merchantId": item.merchant_id,
            "name": item.name,
            "description": item.description,
            "isActive": bool(item.is_active),
            "isDefault": bool(item.is_default),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_item(self, item: MerchantCatalogItem) -> dict:
        return {
            "id": item.id,
            "catalogId": item.catalog_id,
            "name": item.name,
            "description": item.description,
            "category": item.category,
            "price": str(item.price),
            "currency": item.currency,
            "sku": item.sku,
            "stockQuantity": item.stock_quantity,
            "trackInventory": bool(item.track_inventory),
            "isAvailable": bool(item.is_available),
            "isSoldOut": bool(item.is_sold_out),
            "imageUrl": item.image_url,
            "attributes": self._safe_json_loads(item.attributes_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_order(self, item: ShopOrder) -> dict:
        metadata = self._safe_json_loads(item.metadata_json)
        return {
            "id": item.id,
            "merchantId": item.merchant_id,
            "customerUserId": item.customer_user_id,
            "linkedTaskId": item.linked_task_id,
            "deliveryTaskId": item.delivery_task_id,
            "deliveryEscrowId": item.delivery_escrow_id,
            "merchandiseHoldId": item.merchandise_hold_id,
            "beneficiaryName": item.beneficiary_name,
            "beneficiaryPhone": item.beneficiary_phone,
            "orderedForOther": bool(item.ordered_for_other),
            "deliveryAddress": item.delivery_address,
            "deliveryLatitude": item.delivery_latitude,
            "deliveryLongitude": item.delivery_longitude,
            "countryCode": item.country_code,
            "cityName": item.city_name,
            "subtotalAmount": str(item.subtotal_amount),
            "deliveryAmount": str(item.delivery_amount),
            "totalAmount": str(item.total_amount),
            "currency": item.currency,
            "status": item.status,
            "fulfillmentStatus": item.fulfillment_status,
            "dispatchStatus": item.dispatch_status,
            "paymentStatus": item.payment_status,
            "source": item.source,
            "notes": item.notes,
            "customerNote": item.customer_note,
            "cancellationReason": item.cancellation_reason,
            "customerFundedAt": item.customer_funded_at.isoformat() if item.customer_funded_at else None,
            "merchantConfirmedAt": item.merchant_confirmed_at.isoformat() if item.merchant_confirmed_at else None,
            "readyForDispatchAt": item.ready_for_dispatch_at.isoformat() if item.ready_for_dispatch_at else None,
            "deliveredAt": item.delivered_at.isoformat() if item.delivered_at else None,
            "cancelledAt": item.cancelled_at.isoformat() if item.cancelled_at else None,
            "payoutCompletedAt": item.payout_completed_at.isoformat() if item.payout_completed_at else None,
            "metadata": metadata,
            "pricingBreakdown": metadata.get("pricingBreakdown") if isinstance(metadata, dict) else None,
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_order_item(self, item: ShopOrderItem) -> dict:
        return {
            "id": item.id,
            "shopOrderId": item.shop_order_id,
            "catalogItemId": item.catalog_item_id,
            "quantity": item.quantity,
            "unitPrice": str(item.unit_price),
            "lineTotal": str(item.line_total),
            "currency": item.currency,
            "snapshot": self._safe_json_loads(item.snapshot_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_order_event(self, item: ShopOrderEvent) -> dict:
        return {
            "id": item.id,
            "shopOrderId": item.shop_order_id,
            "actorUserId": item.actor_user_id,
            "eventType": item.event_type,
            "eventNote": item.event_note,
            "payload": self._safe_json_loads(item.payload_json),
            "createdAt": item.created_at.isoformat() if item.created_at else None,
        }

    def _serialize_merchant_payout_snapshot(self, snapshot: ShopMerchantPayoutSnapshot, merchant: MerchantPartner) -> dict[str, object]:
        return {
            "id": snapshot.id,
            "periodKey": snapshot.period_key,
            "merchantId": snapshot.merchant_id,
            "merchantName": merchant.public_name,
            "currency": snapshot.currency,
            "orderCount": int(snapshot.order_count),
            "grossGoodsTotal": str(snapshot.gross_goods_total),
            "releasedPayoutTotal": str(snapshot.released_payout_total),
            "refundedGoodsTotal": str(snapshot.refunded_goods_total),
            "pendingGoodsTotal": str(snapshot.pending_goods_total),
            "deliveryFeeTotal": str(snapshot.delivery_fee_total),
            "createdAt": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }
