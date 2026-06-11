from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.observability import logger
from app.core.email import send_welcome_email
from app.core.security import get_password_hash
from app.models.geography import City, ServiceZone
from app.models.food import (
    FoodPaymentHold,
    FoodOrder,
    FoodOrderItem,
    FoodOrderItemModifierSelection,
    RestaurantComboItem,
    RestaurantComboOffer,
    RestaurantPayoutSnapshot,
    RestaurantMenu,
    RestaurantMenuItemModifierGroup,
    RestaurantMenuItemModifierOption,
    RestaurantMenuItem,
    RestaurantPartner,
    RestaurantSpecialClosure,
    RestaurantStaffAssignment,
)
from app.models.task import Task
from app.models.user import User
from app.models.wallet import Escrow, Transaction, Wallet
from app.services.accounting_ledger_service import AccountingLedgerService
from app.services.pricing_engine_service import PricingEngineService
from app.services.task_service import TaskService
from app.services.wallet_service import InsufficientFundsError, WalletService


def _uuid() -> str:
    return str(uuid.uuid4())


class FoodService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.wallet_service = WalletService(db)
        self.task_service = TaskService(db)
        self.pricing_service = PricingEngineService(db)

    def create_restaurant_user(
        self,
        *,
        email: str,
        password: str,
        first_name: str,
        last_name: str,
        country_code: str,
        phone: str | None = None,
    ) -> User:
        email_norm = email.strip().lower()
        if self.db.execute(select(User).where(User.email == email_norm)).scalars().one_or_none():
            raise ValueError("Un utilisateur existe déjà avec cet email.")
        if phone and self.db.execute(select(User).where(User.phone == phone.strip())).scalars().one_or_none():
            raise ValueError("Un utilisateur existe déjà avec ce numéro.")

        user = User(
            id=_uuid(),
            email=email_norm,
            phone=phone.strip() if phone else None,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            full_name=f"{first_name.strip()} {last_name.strip()}".strip(),
            password_hash=get_password_hash(password),
            role="restaurant",
            is_verified=True,
            country_code=country_code.strip().upper(),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        try:
            if user.email and send_welcome_email(user.email, user.full_name or user.first_name or "Bienvenue"):
                user.welcome_email_sent_at = datetime.now(timezone.utc)
                self.db.commit()
        except Exception:
            self.db.rollback()
        return user

    def create_restaurant(
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
        is_temporarily_closed: bool = False,
        prep_buffer_minutes: int = 0,
        launch_status: str = "CONFIGURED",
        opening_hours: dict | None = None,
    ) -> RestaurantPartner:
        if owner_user_id and self.db.get(User, owner_user_id) is None:
            raise ValueError("Utilisateur propriétaire introuvable.")

        restaurant = RestaurantPartner(
            id=_uuid(),
            owner_user_id=owner_user_id,
            service_zone_id=service_zone_id,
            public_name=public_name.strip(),
            legal_name=legal_name.strip() if legal_name else None,
            description=description,
            country_code=country_code.strip().upper(),
            city_name=city_name.strip(),
            address=address,
            latitude=latitude,
            longitude=longitude,
            currency=currency.strip().upper(),
            phone=phone.strip() if phone else None,
            email=email.strip().lower() if email else None,
            accepts_cash_on_delivery=accepts_cash_on_delivery,
            is_active=is_active,
            accepting_orders=accepting_orders,
            is_temporarily_closed=is_temporarily_closed,
            prep_buffer_minutes=prep_buffer_minutes,
            launch_status=launch_status.strip().upper(),
            opening_hours_json=json.dumps(opening_hours) if opening_hours else None,
        )
        self.db.add(restaurant)
        self.db.commit()
        self.db.refresh(restaurant)
        return restaurant

    def list_restaurants(
        self,
        *,
        country_code: str | None = None,
        city_name: str | None = None,
        include_inactive: bool = False,
        for_user_id: str | None = None,
    ) -> list[RestaurantPartner]:
        stmt = select(RestaurantPartner)
        if not include_inactive:
            stmt = stmt.where(
                RestaurantPartner.is_active.is_(True),
                RestaurantPartner.accepting_orders.is_(True),
                RestaurantPartner.is_temporarily_closed.is_(False),
            )
        if country_code:
            stmt = stmt.where(RestaurantPartner.country_code == country_code.strip().upper())
        if city_name:
            stmt = stmt.where(RestaurantPartner.city_name.ilike(f"%{city_name.strip()}%"))
        if for_user_id:
            managed_ids = self._restaurant_ids_for_user(for_user_id)
            stmt = stmt.where(RestaurantPartner.id.in_(managed_ids)) if managed_ids else stmt.where(False)
        return self.db.execute(stmt.order_by(RestaurantPartner.public_name.asc())).scalars().all()

    def discover_restaurants(
        self,
        *,
        country_code: str | None = None,
        city_name: str | None = None,
        reference_latitude: float | None = None,
        reference_longitude: float | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        restaurants = self.list_restaurants(
            country_code=country_code,
            city_name=city_name,
            include_inactive=False,
        )
        payload: list[dict[str, object]] = []
        for restaurant in restaurants:
            supports_target_location = True
            if reference_latitude is not None and reference_longitude is not None:
                supports_target_location = self._restaurant_supports_target(
                    restaurant,
                    reference_latitude=reference_latitude,
                    reference_longitude=reference_longitude,
                )
                if not supports_target_location:
                    continue
            distance_km = self._distance_km(
                reference_latitude,
                reference_longitude,
                restaurant.latitude,
                restaurant.longitude,
            )
            payload.append(
                {
                    "restaurant": restaurant,
                    "distance_km": distance_km,
                    "supports_target_location": supports_target_location,
                }
            )
        payload.sort(
            key=lambda item: (
                item["distance_km"] is None,
                item["distance_km"] if item["distance_km"] is not None else 999999,
                (item["restaurant"].public_name or "").lower(),
            )
        )
        return payload[:limit]

    def get_restaurant(self, restaurant_id: str) -> RestaurantPartner | None:
        return self.db.get(RestaurantPartner, restaurant_id)

    def assign_restaurant_staff(
        self,
        *,
        restaurant_id: str,
        user_id: str,
        staff_role: str = "manager",
        is_primary: bool = False,
    ) -> RestaurantStaffAssignment:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant introuvable.")
        user = self.db.get(User, user_id)
        if user is None:
            raise ValueError("Utilisateur introuvable.")

        existing = self.db.execute(
            select(RestaurantStaffAssignment).where(
                RestaurantStaffAssignment.restaurant_id == restaurant_id,
                RestaurantStaffAssignment.user_id == user_id,
            )
        ).scalars().one_or_none()
        if existing:
            existing.staff_role = staff_role
            existing.is_primary = is_primary
            existing.is_active = True
            self.db.commit()
            self.db.refresh(existing)
            return existing

        assignment = RestaurantStaffAssignment(
            id=_uuid(),
            restaurant_id=restaurant_id,
            user_id=user_id,
            staff_role=staff_role.strip().lower(),
            is_primary=is_primary,
            is_active=True,
        )
        self.db.add(assignment)
        self.db.commit()
        self.db.refresh(assignment)
        return assignment

    def create_menu(
        self,
        *,
        restaurant_id: str,
        name: str,
        description: str | None = None,
        is_active: bool = True,
        is_default: bool = False,
    ) -> RestaurantMenu:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant introuvable.")
        if is_default:
            self.db.execute(
                RestaurantMenu.__table__.update()
                .where(RestaurantMenu.restaurant_id == restaurant_id)
                .values(is_default=False)
            )
        menu = RestaurantMenu(
            id=_uuid(),
            restaurant_id=restaurant_id,
            name=name.strip(),
            description=description,
            is_active=is_active,
            is_default=is_default,
        )
        self.db.add(menu)
        self.db.commit()
        self.db.refresh(menu)
        return menu

    def list_menus(self, restaurant_id: str, *, include_inactive: bool = False) -> list[RestaurantMenu]:
        stmt = select(RestaurantMenu).where(RestaurantMenu.restaurant_id == restaurant_id)
        if not include_inactive:
            stmt = stmt.where(RestaurantMenu.is_active.is_(True))
        return self.db.execute(stmt.order_by(RestaurantMenu.name.asc())).scalars().all()

    def create_menu_item(
        self,
        *,
        menu_id: str,
        name: str,
        price: Decimal,
        currency: str,
        description: str | None = None,
        category: str | None = None,
        prep_minutes: int = 20,
        is_available: bool = True,
        is_sold_out: bool = False,
        track_inventory: bool = False,
        stock_quantity: int | None = None,
        available_from_hour: str | None = None,
        available_to_hour: str | None = None,
        image_url: str | None = None,
    ) -> RestaurantMenuItem:
        menu = self.db.get(RestaurantMenu, menu_id)
        if menu is None:
            raise ValueError("Menu introuvable.")
        item = RestaurantMenuItem(
            id=_uuid(),
            menu_id=menu_id,
            name=name.strip(),
            description=description,
            category=category.strip() if category else None,
            price=Decimal(str(price)),
            currency=currency.strip().upper(),
            prep_minutes=prep_minutes,
            is_available=is_available,
            is_sold_out=is_sold_out,
            track_inventory=track_inventory,
            stock_quantity=stock_quantity,
            available_from_hour=available_from_hour,
            available_to_hour=available_to_hour,
            image_url=image_url,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def list_menu_items(
        self,
        *,
        restaurant_id: str,
        include_unavailable: bool = False,
    ) -> list[RestaurantMenuItem]:
        stmt = (
            select(RestaurantMenuItem)
            .join(RestaurantMenu, RestaurantMenu.id == RestaurantMenuItem.menu_id)
            .where(RestaurantMenu.restaurant_id == restaurant_id)
        )
        if not include_unavailable:
            stmt = stmt.where(
                RestaurantMenuItem.is_available.is_(True),
                RestaurantMenu.is_active.is_(True),
            )
        return self.db.execute(stmt.order_by(RestaurantMenuItem.name.asc())).scalars().all()

    def create_food_order(
        self,
        *,
        customer_user_id: str,
        restaurant_id: str,
        items: list[dict[str, object]],
        delivery_address: str,
        delivery_fee: Decimal | None = None,
        delivery_latitude: float | None = None,
        delivery_longitude: float | None = None,
        notes: str | None = None,
        ordered_for_other: bool = False,
        beneficiary_name: str | None = None,
        beneficiary_phone: str | None = None,
    ) -> FoodOrder:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None or not restaurant.is_active:
            raise ValueError("Restaurant indisponible.")
        if not restaurant.accepting_orders or restaurant.is_temporarily_closed:
            raise ValueError("Ce restaurant n'accepte pas de commandes pour le moment.")
        if not items:
            raise ValueError("Au moins un article est requis.")
        self._assert_restaurant_can_fulfill_order(
            restaurant=restaurant,
            delivery_address=delivery_address,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
        )
        pricing_breakdown = self.pricing_service.quote_food_delivery(
            restaurant=restaurant,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            requested_delivery_fee=delivery_fee,
        )
        final_delivery_fee = Decimal(str(pricing_breakdown["finalFee"]))

        menu_item_ids = [str(item["menu_item_id"]) for item in items]
        combo_offer_ids = [str(item["combo_offer_id"]) for item in items if item.get("combo_offer_id")]
        menu_items = self.db.execute(
            select(RestaurantMenuItem, RestaurantMenu)
            .join(RestaurantMenu, RestaurantMenu.id == RestaurantMenuItem.menu_id)
            .where(RestaurantMenuItem.id.in_(menu_item_ids)) if menu_item_ids else select(RestaurantMenuItem, RestaurantMenu).where(False)
        ).all()
        menu_item_map = {menu_item.id: (menu_item, menu) for menu_item, menu in menu_items}
        combo_offers = self.db.execute(
            select(RestaurantComboOffer).where(RestaurantComboOffer.id.in_(combo_offer_ids))
        ).scalars().all() if combo_offer_ids else []
        combo_offer_map = {combo.id: combo for combo in combo_offers}
        combo_item_rows = self.db.execute(
            select(RestaurantComboItem).where(RestaurantComboItem.combo_offer_id.in_(combo_offer_ids))
        ).scalars().all() if combo_offer_ids else []
        combo_items_by_offer: dict[str, list[RestaurantComboItem]] = {}
        for combo_item in combo_item_rows:
            combo_items_by_offer.setdefault(combo_item.combo_offer_id, []).append(combo_item)

        subtotal = Decimal("0")
        prep_candidates: list[int] = []
        order = FoodOrder(
            id=_uuid(),
            customer_user_id=customer_user_id,
            restaurant_id=restaurant_id,
            status="pending_restaurant",
            payment_status="pending",
            country_code=restaurant.country_code,
            city_name=restaurant.city_name,
            currency=restaurant.currency,
            subtotal=Decimal("0"),
            delivery_fee=final_delivery_fee,
            total_amount=Decimal("0"),
            restaurant_amount=Decimal("0"),
            delivery_amount=final_delivery_fee,
            ordered_for_other=ordered_for_other,
            beneficiary_name=beneficiary_name,
            beneficiary_phone=beneficiary_phone,
            delivery_address=delivery_address,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            notes=notes,
            estimated_prep_minutes=20,
        )
        self.db.add(order)
        self.db.flush()

        for row in items:
            combo_offer_id = str(row.get("combo_offer_id") or "") or None
            menu_item_id = str(row.get("menu_item_id") or "") or None
            quantity = int(row.get("quantity") or 1)
            if quantity <= 0:
                raise ValueError("La quantité doit être positive.")
            if combo_offer_id:
                combo = combo_offer_map.get(combo_offer_id)
                if combo is None or combo.restaurant_id != restaurant_id or not combo.is_active:
                    raise ValueError("Combo introuvable ou indisponible.")
                if not self._is_combo_available_now(combo=combo, restaurant=restaurant):
                    raise ValueError(f"Le combo {combo.name} n'est pas disponible à cette heure.")
                combo_items = combo_items_by_offer.get(combo.id, [])
                if not combo_items:
                    raise ValueError("Ce combo ne contient encore aucun article.")
                prep_minutes = 0
                for combo_item in combo_items:
                    menu_item, menu = menu_item_map.get(combo_item.menu_item_id, (None, None))
                    if menu_item is None:
                        menu_item = self.db.get(RestaurantMenuItem, combo_item.menu_item_id)
                    if menu_item is None:
                        raise ValueError("Un article du combo est introuvable.")
                    if not menu_item.is_available or menu_item.is_sold_out:
                        raise ValueError(f"Un article du combo ({menu_item.name}) n'est plus disponible.")
                    if not self._is_menu_item_available_now(menu_item=menu_item, restaurant=restaurant):
                        raise ValueError(f"Un article du combo ({menu_item.name}) n'est pas disponible à cette heure.")
                    if menu_item.track_inventory:
                        required_quantity = int(combo_item.quantity) * quantity
                        current_stock = int(menu_item.stock_quantity or 0)
                        if current_stock < required_quantity:
                            raise ValueError(f"Stock insuffisant pour l'article {menu_item.name}.")
                        menu_item.stock_quantity = current_stock - required_quantity
                        if menu_item.stock_quantity <= 0:
                            menu_item.is_sold_out = True
                    prep_minutes = max(prep_minutes, int(menu_item.prep_minutes or 0))
                line_total = (Decimal(str(combo.price)) * Decimal(quantity)).quantize(Decimal("0.000001"))
                subtotal += line_total
                prep_candidates.append(prep_minutes)
                order_item = FoodOrderItem(
                    id=_uuid(),
                    food_order_id=order.id,
                    menu_item_id=combo_items[0].menu_item_id,
                    combo_offer_id=combo.id,
                    line_type="combo",
                    item_name=combo.name,
                    quantity=quantity,
                    unit_price=combo.price,
                    modifier_total=Decimal("0"),
                    line_total=line_total,
                )
                self.db.add(order_item)
                self.db.flush()
                continue

            if not menu_item_id or menu_item_id not in menu_item_map:
                raise ValueError("Article menu introuvable.")
            menu_item, menu = menu_item_map[menu_item_id]
            if menu.restaurant_id != restaurant_id:
                raise ValueError("Article invalide pour ce restaurant.")
            if not menu.is_active or not menu_item.is_available or menu_item.is_sold_out:
                raise ValueError("Un des articles demandés n'est plus disponible.")
            if not self._is_menu_item_available_now(menu_item=menu_item, restaurant=restaurant):
                raise ValueError(f"L'article {menu_item.name} n'est pas disponible à cette heure.")
            if menu_item.track_inventory:
                current_stock = int(menu_item.stock_quantity or 0)
                if current_stock < quantity:
                    raise ValueError(f"Stock insuffisant pour l'article {menu_item.name}.")
                menu_item.stock_quantity = current_stock - quantity
                if menu_item.stock_quantity <= 0:
                    menu_item.is_sold_out = True
            modifier_option_ids = [str(option_id) for option_id in (row.get("modifier_option_ids") or [])]
            modifier_total = self._compute_modifier_total(
                menu_item=menu_item,
                currency=restaurant.currency,
                modifier_option_ids=modifier_option_ids,
            )
            line_total = ((Decimal(str(menu_item.price)) + modifier_total) * Decimal(quantity)).quantize(Decimal("0.000001"))
            subtotal += line_total
            prep_candidates.append(menu_item.prep_minutes)
            order_item = FoodOrderItem(
                id=_uuid(),
                food_order_id=order.id,
                menu_item_id=menu_item.id,
                line_type="menu_item",
                item_name=menu_item.name,
                quantity=quantity,
                unit_price=menu_item.price,
                modifier_total=(modifier_total * Decimal(quantity)).quantize(Decimal("0.000001")),
                line_total=line_total,
            )
            self.db.add(order_item)
            self.db.flush()
            if modifier_option_ids:
                self._persist_modifier_selections(
                    order_item_id=order_item.id,
                    menu_item=menu_item,
                    modifier_option_ids=modifier_option_ids,
                )

        order.subtotal = subtotal
        order.restaurant_amount = subtotal
        order.total_amount = subtotal + final_delivery_fee
        order.delivery_amount = final_delivery_fee
        order.estimated_prep_minutes = (max(prep_candidates) if prep_candidates else 20) + int(restaurant.prep_buffer_minutes or 0)
        order.metadata_json = json.dumps(
            self._merge_metadata(
                None,
                {
                    "ordered_for_other": ordered_for_other,
                    "beneficiary_name": beneficiary_name,
                    "beneficiary_phone": beneficiary_phone,
                    "pricingBreakdown": self.pricing_service.serialize_quote(pricing_breakdown),
                },
            )
        )
        self.db.commit()
        self.db.refresh(order)
        return order

    def quote_delivery(
        self,
        *,
        restaurant_id: str,
        delivery_latitude: float | None,
        delivery_longitude: float | None,
        requested_delivery_fee: Decimal | None = None,
    ) -> dict[str, object]:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None or not restaurant.is_active:
            raise ValueError("Restaurant indisponible.")
        quote = self.pricing_service.quote_food_delivery(
            restaurant=restaurant,
            delivery_latitude=delivery_latitude,
            delivery_longitude=delivery_longitude,
            requested_delivery_fee=requested_delivery_fee,
        )
        return self.pricing_service.serialize_quote(quote)

    def fund_order(
        self,
        *,
        order_id: str,
        customer_user_id: str,
    ) -> FoodOrder:
        order = self.db.execute(
            select(FoodOrder).where(FoodOrder.id == order_id).with_for_update()
        ).scalars().one_or_none()
        if order is None:
            raise ValueError("Commande introuvable.")
        if order.customer_user_id != customer_user_id:
            raise ValueError("Seul le client peut financer cette commande.")
        if order.payment_status in {"funded", "completed"}:
            return order

        restaurant = self.db.get(RestaurantPartner, order.restaurant_id)
        if restaurant is None or not restaurant.is_active:
            raise ValueError("Restaurant indisponible.")
        if not restaurant.owner_user_id:
            raise ValueError("Le restaurant n'a pas encore de compte bénéficiaire configuré.")

        if order.meal_hold_id is None:
            meal_hold = self._create_meal_hold_without_commit(
                order=order,
                beneficiary_user_id=restaurant.owner_user_id,
            )
            order.meal_hold_id = meal_hold.id

        if order.delivery_amount > Decimal("0") and order.delivery_task_id is None:
            task = self.task_service.create_task(
                {
                    "title": f"Livraison repas · {restaurant.public_name}",
                    "description": (
                        f"Livraison alimentaire depuis {restaurant.public_name} vers {order.delivery_address}. "
                        f"Commande food {order.id}."
                    ),
                    "price": order.delivery_amount,
                    "currency": order.currency,
                    "latitude": order.delivery_latitude or restaurant.latitude or 0.0,
                    "longitude": order.delivery_longitude or restaurant.longitude or 0.0,
                    "address": order.delivery_address,
                    "status": "OPEN",
                    "created_by": customer_user_id,
                    "service_category": "FOOD_DELIVERY",
                    "mode": "fast",
                    "city": order.city_name,
                    "country": order.country_code,
                },
                commit=False,
            )
            order.delivery_task_id = task.id
            order.dispatch_status = "awaiting_tasker"

        if order.delivery_amount > Decimal("0") and order.delivery_escrow_id is None:
            if not order.delivery_task_id:
                raise ValueError("La tâche de livraison doit exister avant l'escrow food.")
            escrow = self._create_delivery_escrow_without_commit(
                task_id=order.delivery_task_id,
                payer_id=customer_user_id,
                amount=order.delivery_amount,
                currency=order.currency,
            )
            order.delivery_escrow_id = escrow.id

        order.payment_status = "funded"
        self.db.commit()
        self.db.refresh(order)
        return order

    def sync_delivery_assignment(self, *, task_id: str, tasker_id: str) -> FoodOrder | None:
        order = self.db.execute(
            select(FoodOrder).where(FoodOrder.delivery_task_id == task_id).with_for_update()
        ).scalars().one_or_none()
        if order is None:
            return None
        order.dispatch_status = "assigned"
        meta = self._merge_metadata(order.metadata_json, {"delivery_tasker_id": tasker_id})
        order.metadata_json = json.dumps(meta)
        self.db.flush()
        return order

    def finalize_order_from_delivery_task(self, *, task_id: str, commit: bool = False) -> FoodOrder | None:
        order = self.db.execute(
            select(FoodOrder).where(FoodOrder.delivery_task_id == task_id).with_for_update()
        ).scalars().one_or_none()
        if order is None:
            return None
        task = self.db.get(Task, task_id)
        if task is None or task.status != "COMPLETED":
            raise ValueError("La tâche de livraison n'est pas encore finalisée.")
        if order.meal_hold_id:
            meal_hold = self.db.get(FoodPaymentHold, order.meal_hold_id)
            if meal_hold and meal_hold.status == "funded":
                self._release_meal_hold_without_commit(meal_hold)
        order.status = "delivered"
        order.payment_status = "completed"
        order.dispatch_status = "completed"
        order.delivered_at = datetime.now(timezone.utc)
        if commit:
            self.db.commit()
            self.db.refresh(order)
        else:
            self.db.flush()
        return order

    def list_customer_orders(self, customer_user_id: str) -> list[FoodOrder]:
        return self.db.execute(
            select(FoodOrder)
            .where(FoodOrder.customer_user_id == customer_user_id)
            .order_by(FoodOrder.created_at.desc())
        ).scalars().all()

    def list_restaurant_orders(self, actor_user_id: str) -> list[FoodOrder]:
        restaurant_ids = self._restaurant_ids_for_user(actor_user_id)
        if not restaurant_ids:
            return []
        return self.db.execute(
            select(FoodOrder)
            .where(FoodOrder.restaurant_id.in_(restaurant_ids))
            .order_by(FoodOrder.created_at.desc())
        ).scalars().all()

    def get_order(self, order_id: str) -> FoodOrder | None:
        return self.db.get(FoodOrder, order_id)

    def list_order_items(self, order_id: str) -> list[FoodOrderItem]:
        return self.db.execute(
            select(FoodOrderItem)
            .where(FoodOrderItem.food_order_id == order_id)
            .order_by(FoodOrderItem.created_at.asc())
        ).scalars().all()

    def update_order_status_as_restaurant(
        self,
        *,
        order_id: str,
        actor_user_id: str,
        status: str,
        estimated_prep_minutes: int | None = None,
    ) -> FoodOrder:
        order = self.db.get(FoodOrder, order_id)
        if order is None:
            raise ValueError("Commande introuvable.")
        if order.restaurant_id not in self._restaurant_ids_for_user(actor_user_id):
            raise ValueError("Accès restaurant non autorisé.")

        normalized_status = status.strip().lower()
        allowed = {
            "accepted": {"pending_restaurant", "accepted"},
            "preparing": {"accepted", "preparing"},
            "ready_for_pickup": {"accepted", "preparing", "ready_for_pickup"},
            "cancelled": {"pending_restaurant", "accepted", "preparing"},
            "delivered": {"ready_for_pickup", "out_for_delivery", "delivered"},
        }
        current_status = order.status
        if normalized_status not in allowed or current_status not in allowed[normalized_status]:
            raise ValueError("Transition de statut food invalide.")

        if normalized_status in {"accepted", "preparing", "ready_for_pickup"} and order.payment_status != "funded":
            raise ValueError("La commande doit être financée avant traitement restaurant.")

        order.status = normalized_status
        if estimated_prep_minutes is not None:
            order.estimated_prep_minutes = estimated_prep_minutes
        if normalized_status in {"accepted", "preparing", "ready_for_pickup"} and order.restaurant_confirmed_at is None:
            order.restaurant_confirmed_at = datetime.now(timezone.utc)
        if normalized_status == "accepted" and order.dispatch_status == "pending":
            order.dispatch_status = "queued"
        if normalized_status == "ready_for_pickup" and order.dispatch_status in {"pending", "queued"}:
            order.dispatch_status = "awaiting_tasker" if order.delivery_task_id else "ready"
        if normalized_status == "cancelled":
            self._refund_order_funding_without_commit(order)
            order.payment_status = "refunded"
            order.dispatch_status = "cancelled"
        if normalized_status == "delivered":
            if order.delivery_task_id:
                task = self.db.get(Task, order.delivery_task_id)
                if task is None or task.status != "COMPLETED":
                    raise ValueError("La livraison doit être confirmée avant de clore la commande.")
            if order.meal_hold_id:
                meal_hold = self.db.get(FoodPaymentHold, order.meal_hold_id)
                if meal_hold and meal_hold.status == "funded":
                    self._release_meal_hold_without_commit(meal_hold)
            order.delivered_at = datetime.now(timezone.utc)
            order.payment_status = "completed"
            order.dispatch_status = "completed"
        self.db.commit()
        self.db.refresh(order)
        return order

    def update_restaurant_operations(
        self,
        *,
        restaurant_id: str,
        service_zone_id: str | None = None,
        accepting_orders: bool | None = None,
        is_temporarily_closed: bool | None = None,
        prep_buffer_minutes: int | None = None,
        opening_hours: dict | None = None,
    ) -> RestaurantPartner:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant introuvable.")
        if service_zone_id is not None:
            restaurant.service_zone_id = service_zone_id or None
        if accepting_orders is not None:
            restaurant.accepting_orders = accepting_orders
        if is_temporarily_closed is not None:
            restaurant.is_temporarily_closed = is_temporarily_closed
        if prep_buffer_minutes is not None:
            restaurant.prep_buffer_minutes = prep_buffer_minutes
        if opening_hours is not None:
            restaurant.opening_hours_json = json.dumps(opening_hours)
        self.db.commit()
        self.db.refresh(restaurant)
        return restaurant

    def update_menu_item_operations(
        self,
        *,
        item_id: str,
        is_available: bool | None = None,
        is_sold_out: bool | None = None,
        track_inventory: bool | None = None,
        stock_quantity: int | None = None,
        available_from_hour: str | None = None,
        available_to_hour: str | None = None,
    ) -> RestaurantMenuItem:
        item = self.db.get(RestaurantMenuItem, item_id)
        if item is None:
            raise ValueError("Article introuvable.")
        if is_available is not None:
            item.is_available = is_available
        if is_sold_out is not None:
            item.is_sold_out = is_sold_out
        if track_inventory is not None:
            item.track_inventory = track_inventory
        if stock_quantity is not None:
            item.stock_quantity = stock_quantity
            if stock_quantity <= 0:
                item.is_sold_out = True
        if available_from_hour is not None:
            item.available_from_hour = available_from_hour
        if available_to_hour is not None:
            item.available_to_hour = available_to_hour
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_dispatch_candidates(
        self,
        *,
        tasker_latitude: float,
        tasker_longitude: float,
        country_code: str | None = None,
        city_name: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, object]]:
        rows = self.db.execute(
            select(FoodOrder, RestaurantPartner, Task)
            .join(RestaurantPartner, RestaurantPartner.id == FoodOrder.restaurant_id)
            .join(Task, Task.id == FoodOrder.delivery_task_id)
            .where(
                FoodOrder.status.in_(["accepted", "preparing", "ready_for_pickup"]),
                FoodOrder.dispatch_status.in_(["queued", "awaiting_tasker"]),
                Task.status == "OPEN",
            )
            .order_by(FoodOrder.created_at.asc())
        ).all()

        candidates: list[dict[str, object]] = []
        for order, restaurant, task in rows:
            if country_code and order.country_code != country_code.upper():
                continue
            if city_name and order.city_name.lower() != city_name.strip().lower():
                continue
            restaurant_distance = self._distance_km(
                tasker_latitude,
                tasker_longitude,
                restaurant.latitude,
                restaurant.longitude,
            )
            delivery_distance = self._distance_km(
                tasker_latitude,
                tasker_longitude,
                order.delivery_latitude,
                order.delivery_longitude,
            )
            score = self._dispatch_score(
                restaurant_distance_km=restaurant_distance,
                delivery_distance_km=delivery_distance,
                created_at=order.created_at,
                is_ready=order.status == "ready_for_pickup",
            )
            candidates.append(
                {
                    "food_order_id": order.id,
                    "delivery_task_id": task.id,
                    "restaurant_id": restaurant.id,
                    "restaurant_name": restaurant.public_name,
                    "country_code": order.country_code,
                    "city_name": order.city_name,
                    "status": order.status,
                    "dispatch_status": order.dispatch_status,
                    "estimated_prep_minutes": order.estimated_prep_minutes,
                    "restaurant_distance_km": restaurant_distance,
                    "delivery_distance_km": delivery_distance,
                    "dispatch_score": score,
                    "task_price": str(task.price),
                    "currency": task.currency,
                    "created_at": order.created_at.isoformat() if order.created_at else None,
                }
            )

        candidates.sort(key=lambda item: float(item["dispatch_score"]), reverse=True)
        return candidates[:limit]

    def build_restaurant_payout_snapshots(
        self,
        *,
        period_key: str | None = None,
        restaurant_id: str | None = None,
    ) -> list[dict[str, object]]:
        target_period = period_key or datetime.now(timezone.utc).strftime("%Y-%m")
        rows = self.db.execute(
            select(FoodOrder, RestaurantPartner, FoodPaymentHold)
            .join(RestaurantPartner, RestaurantPartner.id == FoodOrder.restaurant_id)
            .join(FoodPaymentHold, FoodPaymentHold.id == FoodOrder.meal_hold_id, isouter=True)
            .order_by(FoodOrder.created_at.asc())
        ).all()

        aggregates: dict[tuple[str, str], dict[str, object]] = {}
        for order, restaurant, hold in rows:
            created_at = order.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            if created_at.strftime("%Y-%m") != target_period:
                continue
            if restaurant_id and restaurant.id != restaurant_id:
                continue
            key = (restaurant.id, order.currency)
            bucket = aggregates.setdefault(
                key,
                {
                    "restaurant": restaurant,
                    "currency": order.currency,
                    "order_count": 0,
                    "gross_meal_total": Decimal("0"),
                    "released_payout_total": Decimal("0"),
                    "refunded_meal_total": Decimal("0"),
                    "pending_meal_total": Decimal("0"),
                    "delivery_fee_total": Decimal("0"),
                },
            )
            bucket["order_count"] += 1
            bucket["gross_meal_total"] += Decimal(str(order.restaurant_amount))
            bucket["delivery_fee_total"] += Decimal(str(order.delivery_amount))
            if hold is None:
                bucket["pending_meal_total"] += Decimal(str(order.restaurant_amount))
            elif hold.status == "released":
                bucket["released_payout_total"] += Decimal(str(hold.amount))
            elif hold.status == "refunded":
                bucket["refunded_meal_total"] += Decimal(str(hold.amount))
            else:
                bucket["pending_meal_total"] += Decimal(str(hold.amount))

        payloads: list[dict[str, object]] = []
        for (current_restaurant_id, current_currency), bucket in aggregates.items():
            row = self.db.execute(
                select(RestaurantPayoutSnapshot).where(
                    RestaurantPayoutSnapshot.period_key == target_period,
                    RestaurantPayoutSnapshot.restaurant_id == current_restaurant_id,
                    RestaurantPayoutSnapshot.currency == current_currency,
                )
            ).scalars().one_or_none()
            metadata_json = json.dumps(
                {
                    "restaurant_name": bucket["restaurant"].public_name,
                    "generated_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if row is None:
                row = RestaurantPayoutSnapshot(
                    id=_uuid(),
                    period_key=target_period,
                    restaurant_id=current_restaurant_id,
                    currency=current_currency,
                    order_count=int(bucket["order_count"]),
                    gross_meal_total=bucket["gross_meal_total"],
                    released_payout_total=bucket["released_payout_total"],
                    refunded_meal_total=bucket["refunded_meal_total"],
                    pending_meal_total=bucket["pending_meal_total"],
                    delivery_fee_total=bucket["delivery_fee_total"],
                    metadata_json=metadata_json,
                )
                self.db.add(row)
            else:
                row.order_count = int(bucket["order_count"])
                row.gross_meal_total = bucket["gross_meal_total"]
                row.released_payout_total = bucket["released_payout_total"]
                row.refunded_meal_total = bucket["refunded_meal_total"]
                row.pending_meal_total = bucket["pending_meal_total"]
                row.delivery_fee_total = bucket["delivery_fee_total"]
                row.metadata_json = metadata_json
            payloads.append(self._serialize_restaurant_payout_snapshot(row, bucket["restaurant"]))

        self.db.commit()
        return payloads

    def list_restaurant_payout_snapshots(
        self,
        *,
        period_key: str | None = None,
        restaurant_id: str | None = None,
        currency: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, object]]:
        stmt = (
            select(RestaurantPayoutSnapshot, RestaurantPartner)
            .join(RestaurantPartner, RestaurantPartner.id == RestaurantPayoutSnapshot.restaurant_id)
            .order_by(RestaurantPayoutSnapshot.period_key.desc(), RestaurantPartner.public_name.asc())
            .limit(limit)
        )
        if period_key:
            stmt = stmt.where(RestaurantPayoutSnapshot.period_key == period_key)
        if restaurant_id:
            stmt = stmt.where(RestaurantPayoutSnapshot.restaurant_id == restaurant_id)
        if currency:
            stmt = stmt.where(RestaurantPayoutSnapshot.currency == currency.upper())
        rows = self.db.execute(stmt).all()
        return [self._serialize_restaurant_payout_snapshot(snapshot, restaurant) for snapshot, restaurant in rows]

    def create_modifier_group(
        self,
        *,
        menu_item_id: str,
        name: str,
        is_required: bool = False,
        min_select: int = 0,
        max_select: int = 1,
        is_active: bool = True,
    ) -> RestaurantMenuItemModifierGroup:
        item = self.db.get(RestaurantMenuItem, menu_item_id)
        if item is None:
            raise ValueError("Article introuvable.")
        group = RestaurantMenuItemModifierGroup(
            id=_uuid(),
            menu_item_id=menu_item_id,
            name=name.strip(),
            is_required=is_required,
            min_select=min_select,
            max_select=max_select,
            is_active=is_active,
        )
        self.db.add(group)
        self.db.commit()
        self.db.refresh(group)
        return group

    def create_modifier_option(
        self,
        *,
        modifier_group_id: str,
        name: str,
        currency: str,
        price_delta: Decimal = Decimal("0"),
        is_default: bool = False,
        is_active: bool = True,
    ) -> RestaurantMenuItemModifierOption:
        group = self.db.get(RestaurantMenuItemModifierGroup, modifier_group_id)
        if group is None:
            raise ValueError("Groupe de modificateurs introuvable.")
        option = RestaurantMenuItemModifierOption(
            id=_uuid(),
            modifier_group_id=modifier_group_id,
            name=name.strip(),
            currency=currency.strip().upper(),
            price_delta=Decimal(str(price_delta)),
            is_default=is_default,
            is_active=is_active,
        )
        self.db.add(option)
        self.db.commit()
        self.db.refresh(option)
        return option

    def list_modifier_groups(self, *, menu_item_id: str) -> list[RestaurantMenuItemModifierGroup]:
        return self.db.execute(
            select(RestaurantMenuItemModifierGroup)
            .where(RestaurantMenuItemModifierGroup.menu_item_id == menu_item_id)
            .order_by(RestaurantMenuItemModifierGroup.created_at.asc())
        ).scalars().all()

    def list_modifier_options(self, *, modifier_group_id: str) -> list[RestaurantMenuItemModifierOption]:
        return self.db.execute(
            select(RestaurantMenuItemModifierOption)
            .where(RestaurantMenuItemModifierOption.modifier_group_id == modifier_group_id)
            .order_by(RestaurantMenuItemModifierOption.created_at.asc())
        ).scalars().all()

    def create_special_closure(
        self,
        *,
        restaurant_id: str,
        starts_at: datetime,
        ends_at: datetime,
        reason: str | None = None,
        is_active: bool = True,
    ) -> RestaurantSpecialClosure:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant introuvable.")
        if ends_at <= starts_at:
            raise ValueError("La fin de fermeture doit être après le début.")
        closure = RestaurantSpecialClosure(
            id=_uuid(),
            restaurant_id=restaurant_id,
            reason=reason,
            starts_at=starts_at,
            ends_at=ends_at,
            is_active=is_active,
        )
        self.db.add(closure)
        self.db.commit()
        self.db.refresh(closure)
        return closure

    def list_special_closures(self, *, restaurant_id: str) -> list[RestaurantSpecialClosure]:
        return self.db.execute(
            select(RestaurantSpecialClosure)
            .where(RestaurantSpecialClosure.restaurant_id == restaurant_id)
            .order_by(RestaurantSpecialClosure.starts_at.asc())
        ).scalars().all()

    def create_combo_offer(
        self,
        *,
        restaurant_id: str,
        name: str,
        price: Decimal,
        currency: str,
        description: str | None = None,
        is_active: bool = True,
        available_from_hour: str | None = None,
        available_to_hour: str | None = None,
    ) -> RestaurantComboOffer:
        restaurant = self.db.get(RestaurantPartner, restaurant_id)
        if restaurant is None:
            raise ValueError("Restaurant introuvable.")
        combo = RestaurantComboOffer(
            id=_uuid(),
            restaurant_id=restaurant_id,
            name=name.strip(),
            description=description,
            price=Decimal(str(price)),
            currency=currency.strip().upper(),
            is_active=is_active,
            available_from_hour=available_from_hour,
            available_to_hour=available_to_hour,
        )
        self.db.add(combo)
        self.db.commit()
        self.db.refresh(combo)
        return combo

    def add_combo_item(
        self,
        *,
        combo_offer_id: str,
        menu_item_id: str,
        quantity: int = 1,
    ) -> RestaurantComboItem:
        combo = self.db.get(RestaurantComboOffer, combo_offer_id)
        item = self.db.get(RestaurantMenuItem, menu_item_id)
        if combo is None or item is None:
            raise ValueError("Combo ou article introuvable.")
        row = RestaurantComboItem(
            id=_uuid(),
            combo_offer_id=combo_offer_id,
            menu_item_id=menu_item_id,
            quantity=quantity,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def list_combo_offers(self, *, restaurant_id: str) -> list[RestaurantComboOffer]:
        return self.db.execute(
            select(RestaurantComboOffer)
            .where(RestaurantComboOffer.restaurant_id == restaurant_id)
            .order_by(RestaurantComboOffer.created_at.asc())
        ).scalars().all()

    def list_combo_items(self, *, combo_offer_id: str) -> list[RestaurantComboItem]:
        return self.db.execute(
            select(RestaurantComboItem)
            .where(RestaurantComboItem.combo_offer_id == combo_offer_id)
            .order_by(RestaurantComboItem.created_at.asc())
        ).scalars().all()

    def sync_payout_snapshots_to_accounting(
        self,
        *,
        period_key: str | None = None,
        restaurant_id: str | None = None,
    ) -> dict[str, object]:
        snapshots = self.build_restaurant_payout_snapshots(period_key=period_key, restaurant_id=restaurant_id)
        result = AccountingLedgerService(self.db).sync_restaurant_payout_snapshots(
            period_key=period_key,
            restaurant_id=restaurant_id,
        )
        return {
            "snapshots_count": len(snapshots),
            "ledger_sync": result,
        }

    def _create_meal_hold_without_commit(
        self,
        *,
        order: FoodOrder,
        beneficiary_user_id: str,
    ) -> FoodPaymentHold:
        existing = self.db.execute(
            select(FoodPaymentHold).where(FoodPaymentHold.food_order_id == order.id).with_for_update()
        ).scalars().one_or_none()
        if existing is not None:
            return existing

        wallet = self.wallet_service._get_or_create_wallet(order.customer_user_id, order.currency, for_update=True)
        if wallet.balance < order.restaurant_amount:
            raise InsufficientFundsError(
                f"Solde insuffisant : {wallet.balance} {order.currency} < {order.restaurant_amount} {order.currency}"
            )

        tx = Transaction(
            id=_uuid(),
            wallet_id=wallet.id,
            type="debit",
            amount=order.restaurant_amount,
            status="completed",
            reference=f"food_meal_hold:{order.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "food_meal_hold",
                    "food_order_id": order.id,
                    "restaurant_id": order.restaurant_id,
                }
            ),
        )
        wallet.balance -= order.restaurant_amount
        self.db.add(tx)
        self.db.flush()

        hold = FoodPaymentHold(
            id=_uuid(),
            food_order_id=order.id,
            payer_user_id=order.customer_user_id,
            beneficiary_user_id=beneficiary_user_id,
            amount=order.restaurant_amount,
            currency=order.currency,
            status="funded",
            funding_tx_id=tx.id,
            metadata_json=json.dumps({"restaurant_id": order.restaurant_id}),
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
            reference=f"escrow_fund:{escrow_id}",
            provider="internal",
            metadata_json=json.dumps({"type": "escrow_fund", "escrow_id": escrow_id, "task_id": task_id}),
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

    def _release_meal_hold_without_commit(self, hold: FoodPaymentHold) -> FoodPaymentHold:
        if hold.status != "funded":
            return hold
        beneficiary_wallet = self.wallet_service._get_or_create_wallet(hold.beneficiary_user_id, hold.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=beneficiary_wallet.id,
            type="credit",
            amount=hold.amount,
            status="completed",
            reference=f"food_meal_release:{hold.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "food_meal_release",
                    "food_order_id": hold.food_order_id,
                    "hold_id": hold.id,
                }
            ),
        )
        beneficiary_wallet.balance += hold.amount
        self.db.add(tx)
        self.db.flush()
        hold.settlement_tx_id = tx.id
        hold.status = "released"
        hold.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return hold

    def _refund_meal_hold_without_commit(self, hold: FoodPaymentHold) -> FoodPaymentHold:
        if hold.status != "funded":
            return hold
        payer_wallet = self.wallet_service._get_or_create_wallet(hold.payer_user_id, hold.currency, for_update=True)
        tx = Transaction(
            id=_uuid(),
            wallet_id=payer_wallet.id,
            type="credit",
            amount=hold.amount,
            status="completed",
            reference=f"food_meal_refund:{hold.id}",
            provider="internal",
            metadata_json=json.dumps(
                {
                    "type": "food_meal_refund",
                    "food_order_id": hold.food_order_id,
                    "hold_id": hold.id,
                }
            ),
        )
        payer_wallet.balance += hold.amount
        self.db.add(tx)
        self.db.flush()
        hold.settlement_tx_id = tx.id
        hold.status = "refunded"
        hold.updated_at = datetime.now(timezone.utc)
        self.db.flush()
        return hold

    def _refund_order_funding_without_commit(self, order: FoodOrder) -> None:
        if order.meal_hold_id:
            hold = self.db.get(FoodPaymentHold, order.meal_hold_id)
            if hold and hold.status == "funded":
                self._refund_meal_hold_without_commit(hold)
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
                    reference=f"food_delivery_refund:{escrow.id}",
                    provider="internal",
                    metadata_json=json.dumps(
                        {
                            "type": "food_delivery_refund",
                            "food_order_id": order.id,
                            "escrow_id": escrow.id,
                        }
                    ),
                )
                payer_wallet.balance += escrow.amount
                self.db.add(tx)
                self.db.flush()
                escrow.status = "refunded"
                escrow.settlement_tx_id = tx.id

        if order.delivery_task_id:
            task = self.db.execute(
                select(Task).where(Task.id == order.delivery_task_id).with_for_update()
            ).scalars().one_or_none()
            if task and task.status in {"OPEN", "ASSIGNED", "PAUSED", "PENDING_VALIDATION"}:
                task.status = "CANCELLED"
                self.db.flush()
        self._restore_inventory_for_order(order.id)

    def _restore_inventory_for_order(self, order_id: str) -> None:
        items = self.db.execute(
            select(FoodOrderItem).where(FoodOrderItem.food_order_id == order_id)
        ).scalars().all()
        if not items:
            return
        menu_item_ids = [item.menu_item_id for item in items]
        menu_items = {
            item.id: item
            for item in self.db.execute(
                select(RestaurantMenuItem).where(RestaurantMenuItem.id.in_(menu_item_ids)).with_for_update()
            ).scalars().all()
        }
        for order_item in items:
            if order_item.line_type == "combo" and order_item.combo_offer_id:
                combo_items = self.list_combo_items(combo_offer_id=order_item.combo_offer_id)
                combo_menu_ids = [combo_item.menu_item_id for combo_item in combo_items]
                combo_menu_items = {
                    item.id: item
                    for item in self.db.execute(
                        select(RestaurantMenuItem).where(RestaurantMenuItem.id.in_(combo_menu_ids)).with_for_update()
                    ).scalars().all()
                }
                for combo_item in combo_items:
                    menu_item = combo_menu_items.get(combo_item.menu_item_id)
                    if not menu_item or not menu_item.track_inventory:
                        continue
                    menu_item.stock_quantity = int(menu_item.stock_quantity or 0) + int(combo_item.quantity) * int(order_item.quantity)
                    if menu_item.stock_quantity > 0:
                        menu_item.is_sold_out = False
                continue
            menu_item = menu_items.get(order_item.menu_item_id)
            if not menu_item or not menu_item.track_inventory:
                continue
            menu_item.stock_quantity = int(menu_item.stock_quantity or 0) + int(order_item.quantity)
            if menu_item.stock_quantity > 0:
                menu_item.is_sold_out = False
        self.db.flush()

    def _assert_restaurant_can_fulfill_order(
        self,
        *,
        restaurant: RestaurantPartner,
        delivery_address: str,
        delivery_latitude: float | None,
        delivery_longitude: float | None,
    ) -> None:
        _ = delivery_address
        if restaurant.service_zone_id:
            zone = self.db.get(ServiceZone, restaurant.service_zone_id)
            if zone is not None and zone.is_active and zone.launch_status == "ACTIVE":
                coverage_raw = getattr(zone, "coverage_json", None) or getattr(zone, "coverage", None)
                polygon = self._extract_polygon_points(coverage_raw)
                if polygon and delivery_latitude is not None and delivery_longitude is not None:
                    if not self._point_in_polygon(delivery_latitude, delivery_longitude, polygon):
                        raise ValueError("Cette adresse est hors de la zone polygonale de service du restaurant.")
                if (
                    zone.center_latitude is not None
                    and zone.center_longitude is not None
                    and zone.radius_km is not None
                    and delivery_latitude is not None
                    and delivery_longitude is not None
                ):
                    distance = self._distance_km(
                        delivery_latitude,
                        delivery_longitude,
                        zone.center_latitude,
                        zone.center_longitude,
                    )
                    if distance is not None and distance > float(zone.radius_km):
                        raise ValueError("Cette adresse est hors de la zone de service du restaurant.")
        if not self._is_restaurant_open_now(restaurant):
            raise ValueError("Le restaurant est actuellement fermé pour cette plage horaire.")

    def _restaurant_supports_target(
        self,
        restaurant: RestaurantPartner,
        *,
        reference_latitude: float,
        reference_longitude: float,
    ) -> bool:
        if restaurant.service_zone_id:
            zone = self.db.get(ServiceZone, restaurant.service_zone_id)
            if zone is not None and zone.is_active:
                coverage_raw = getattr(zone, "coverage_json", None) or getattr(zone, "coverage", None)
                polygon = self._extract_polygon_points(coverage_raw)
                if polygon:
                    return self._point_in_polygon(reference_latitude, reference_longitude, polygon)
                if (
                    zone.center_latitude is not None
                    and zone.center_longitude is not None
                    and zone.radius_km is not None
                ):
                    distance = self._distance_km(
                        reference_latitude,
                        reference_longitude,
                        zone.center_latitude,
                        zone.center_longitude,
                    )
                    if distance is not None:
                        return distance <= float(zone.radius_km)
        distance = self._distance_km(
            reference_latitude,
            reference_longitude,
            restaurant.latitude,
            restaurant.longitude,
        )
        return distance is None or distance <= 25.0

    def _compute_modifier_total(
        self,
        *,
        menu_item: RestaurantMenuItem,
        currency: str,
        modifier_option_ids: list[str],
    ) -> Decimal:
        groups = self.list_modifier_groups(menu_item_id=menu_item.id)
        if not groups and modifier_option_ids:
            raise ValueError("Cet article n'accepte pas de modificateurs.")

        options = self.db.execute(
            select(RestaurantMenuItemModifierOption)
            .where(RestaurantMenuItemModifierOption.id.in_(modifier_option_ids))
        ).scalars().all()
        option_map = {option.id: option for option in options}
        selections_by_group: dict[str, list[RestaurantMenuItemModifierOption]] = {}
        total = Decimal("0")

        for option_id in modifier_option_ids:
            option = option_map.get(option_id)
            if option is None or not option.is_active:
                raise ValueError("Option de modificateur invalide.")
            if option.currency != currency.upper():
                raise ValueError("Devise de modificateur incohérente.")
            selections_by_group.setdefault(option.modifier_group_id, []).append(option)
            total += Decimal(str(option.price_delta))

        for group in groups:
            selections = selections_by_group.get(group.id, [])
            count = len(selections)
            if group.is_required and count < max(1, int(group.min_select or 0)):
                raise ValueError(f"Le groupe obligatoire '{group.name}' est incomplet.")
            if count < int(group.min_select or 0):
                raise ValueError(f"Le minimum de sélection n'est pas respecté pour '{group.name}'.")
            if count > int(group.max_select or 1):
                raise ValueError(f"Le maximum de sélection est dépassé pour '{group.name}'.")
        return total.quantize(Decimal("0.000001"))

    def _persist_modifier_selections(
        self,
        *,
        order_item_id: str,
        menu_item: RestaurantMenuItem,
        modifier_option_ids: list[str],
    ) -> None:
        groups = {group.id: group for group in self.list_modifier_groups(menu_item_id=menu_item.id)}
        options = self.db.execute(
            select(RestaurantMenuItemModifierOption)
            .where(RestaurantMenuItemModifierOption.id.in_(modifier_option_ids))
        ).scalars().all()
        for option in options:
            group = groups.get(option.modifier_group_id)
            if group is None:
                raise ValueError("Le modificateur ne correspond pas à cet article.")
            self.db.add(
                FoodOrderItemModifierSelection(
                    id=_uuid(),
                    food_order_item_id=order_item_id,
                    modifier_group_id=group.id,
                    modifier_option_id=option.id,
                    group_name=group.name,
                    option_name=option.name,
                    price_delta=option.price_delta,
                )
            )
        self.db.flush()

    def _is_restaurant_open_now(self, restaurant: RestaurantPartner) -> bool:
        if restaurant.is_temporarily_closed or not restaurant.accepting_orders:
            return False
        if self._is_restaurant_in_special_closure(restaurant):
            return False
        if not restaurant.opening_hours_json:
            return True
        try:
            opening_hours = json.loads(restaurant.opening_hours_json)
        except Exception:
            logger.warning("food:invalid_opening_hours restaurant_id={}", restaurant.id)
            return True
        if not isinstance(opening_hours, dict):
            return True

        tz_name = self._resolve_restaurant_timezone(restaurant)
        local_now = datetime.now(ZoneInfo(tz_name))
        weekday_key = local_now.strftime("%a").lower()[:3]
        slots = opening_hours.get(weekday_key) or opening_hours.get(local_now.strftime("%A").lower()) or []
        if not slots:
            return False
        current_hhmm = local_now.strftime("%H:%M")
        for slot in slots:
            if not isinstance(slot, dict):
                continue
            start = str(slot.get("start") or "")
            end = str(slot.get("end") or "")
            if start and end and start <= current_hhmm <= end:
                return True
        return False

    def _resolve_restaurant_timezone(self, restaurant: RestaurantPartner) -> str:
        city = self.db.execute(
            select(City).where(
                City.country_code == restaurant.country_code,
                City.name.ilike(restaurant.city_name),
            )
        ).scalars().first()
        if city and getattr(city, "timezone_name", None):
            return str(city.timezone_name)
        return "UTC"

    def _is_menu_item_available_now(self, *, menu_item: RestaurantMenuItem, restaurant: RestaurantPartner) -> bool:
        if not menu_item.available_from_hour or not menu_item.available_to_hour:
            return True
        tz_name = self._resolve_restaurant_timezone(restaurant)
        local_now = datetime.now(ZoneInfo(tz_name)).strftime("%H:%M")
        return str(menu_item.available_from_hour) <= local_now <= str(menu_item.available_to_hour)

    def _is_combo_available_now(self, *, combo: RestaurantComboOffer, restaurant: RestaurantPartner) -> bool:
        if not combo.available_from_hour or not combo.available_to_hour:
            return True
        tz_name = self._resolve_restaurant_timezone(restaurant)
        local_now = datetime.now(ZoneInfo(tz_name)).strftime("%H:%M")
        return str(combo.available_from_hour) <= local_now <= str(combo.available_to_hour)

    def _is_restaurant_in_special_closure(self, restaurant: RestaurantPartner) -> bool:
        tz_name = self._resolve_restaurant_timezone(restaurant)
        local_now = datetime.now(ZoneInfo(tz_name))
        closures = self.db.execute(
            select(RestaurantSpecialClosure).where(
                RestaurantSpecialClosure.restaurant_id == restaurant.id,
                RestaurantSpecialClosure.is_active.is_(True),
            )
        ).scalars().all()
        for closure in closures:
            starts_at = closure.starts_at if closure.starts_at.tzinfo else closure.starts_at.replace(tzinfo=timezone.utc)
            ends_at = closure.ends_at if closure.ends_at.tzinfo else closure.ends_at.replace(tzinfo=timezone.utc)
            local_start = starts_at.astimezone(ZoneInfo(tz_name))
            local_end = ends_at.astimezone(ZoneInfo(tz_name))
            if local_start <= local_now <= local_end:
                return True
        return False

    @staticmethod
    def _extract_polygon_points(raw: object) -> list[tuple[float, float]]:
        if not raw:
            return []
        try:
            payload = json.loads(raw) if isinstance(raw, str) else raw
        except Exception:
            return []
        points = []
        if isinstance(payload, dict):
            if isinstance(payload.get("points"), list):
                points = payload["points"]
            elif isinstance(payload.get("coordinates"), list):
                coords = payload["coordinates"]
                if coords and isinstance(coords[0], list) and coords and isinstance(coords[0][0], (list, tuple)):
                    points = coords[0]
                else:
                    points = coords
        elif isinstance(payload, list):
            points = payload
        normalized: list[tuple[float, float]] = []
        for point in points:
            if not isinstance(point, (list, tuple)) or len(point) < 2:
                continue
            a = float(point[0])
            b = float(point[1])
            if abs(a) <= 90 and abs(b) <= 180:
                normalized.append((a, b))
            else:
                normalized.append((b, a))
        return normalized

    @staticmethod
    def _point_in_polygon(lat: float, lng: float, polygon: list[tuple[float, float]]) -> bool:
        if len(polygon) < 3:
            return False
        inside = False
        j = len(polygon) - 1
        for i in range(len(polygon)):
            yi, xi = polygon[i]
            yj, xj = polygon[j]
            intersects = ((xi > lng) != (xj > lng)) and (
                lat < (yj - yi) * (lng - xi) / ((xj - xi) or 1e-9) + yi
            )
            if intersects:
                inside = not inside
            j = i
        return inside

    @staticmethod
    def _distance_km(lat1: float | None, lon1: float | None, lat2: float | None, lon2: float | None) -> float | None:
        if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
            return None
        return TaskService._haversine(lat1, lon1, lat2, lon2)

    @staticmethod
    def _dispatch_score(
        *,
        restaurant_distance_km: float | None,
        delivery_distance_km: float | None,
        created_at: datetime | None,
        is_ready: bool,
    ) -> float:
        score = 0.0
        if is_ready:
            score += 40.0
        if restaurant_distance_km is not None:
            score += max(0.0, 30.0 - restaurant_distance_km)
        if delivery_distance_km is not None:
            score += max(0.0, 20.0 - delivery_distance_km / 2.0)
        if created_at:
            now = datetime.now(timezone.utc)
            created_value = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
            wait_minutes = max(0.0, (now - created_value).total_seconds() / 60.0)
            score += min(20.0, wait_minutes / 3.0)
        return round(score, 3)

    @staticmethod
    def _serialize_restaurant_payout_snapshot(snapshot: RestaurantPayoutSnapshot, restaurant: RestaurantPartner) -> dict[str, object]:
        return {
            "id": snapshot.id,
            "period_key": snapshot.period_key,
            "restaurant_id": snapshot.restaurant_id,
            "restaurant_name": restaurant.public_name,
            "currency": snapshot.currency,
            "order_count": int(snapshot.order_count),
            "gross_meal_total": str(snapshot.gross_meal_total),
            "released_payout_total": str(snapshot.released_payout_total),
            "refunded_meal_total": str(snapshot.refunded_meal_total),
            "pending_meal_total": str(snapshot.pending_meal_total),
            "delivery_fee_total": str(snapshot.delivery_fee_total),
            "created_at": snapshot.created_at.isoformat() if snapshot.created_at else None,
        }

    @staticmethod
    def _merge_metadata(existing_raw: str | None, extra: dict[str, object]) -> dict[str, object]:
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

    def _restaurant_ids_for_user(self, user_id: str) -> list[str]:
        owned_rows = self.db.execute(
            select(RestaurantPartner.id).where(RestaurantPartner.owner_user_id == user_id)
        ).all()
        assignment_rows = self.db.execute(
            select(RestaurantStaffAssignment.restaurant_id).where(
                RestaurantStaffAssignment.user_id == user_id,
                RestaurantStaffAssignment.is_active.is_(True),
            )
        ).all()
        restaurant_ids = {row[0] for row in owned_rows + assignment_rows}
        return sorted(restaurant_ids)
