from __future__ import annotations

import json
import math
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.food import RestaurantPartner
from app.models.geography import Continent, ServiceZone
from app.models.location_config import Country
from app.models.shop import MerchantPartner
from app.models.vtc import VtcFleetOperator


def _to_decimal(value: Decimal | float | int | str | None, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _quantize_money(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


class PricingEngineService:
    def __init__(self, db: Session):
        self.db = db

    def quote_food_delivery(
        self,
        *,
        restaurant: RestaurantPartner,
        delivery_latitude: float | None,
        delivery_longitude: float | None,
        requested_delivery_fee: Decimal | None = None,
    ) -> dict[str, object]:
        zone = self._resolve_zone(
            module_code="FOOD",
            preferred_zone_id=restaurant.service_zone_id,
            country_code=restaurant.country_code,
            city_name=restaurant.city_name,
            latitude=delivery_latitude,
            longitude=delivery_longitude,
        )
        profile, source = self._resolve_delivery_profile(
            zone=zone,
            country_code=restaurant.country_code,
            partner_metadata_raw=restaurant.metadata_json,
            currency=restaurant.currency,
        )
        distance_km = self._distance_km(
            restaurant.latitude,
            restaurant.longitude,
            delivery_latitude,
            delivery_longitude,
        )
        return self._build_delivery_quote(
            module_code="FOOD",
            currency=restaurant.currency,
            zone=zone,
            profile=profile,
            source=source,
            distance_km=distance_km,
            requested_delivery_fee=requested_delivery_fee,
        )

    def quote_shop_delivery(
        self,
        *,
        merchant: MerchantPartner,
        delivery_latitude: float | None,
        delivery_longitude: float | None,
        requested_delivery_fee: Decimal | None = None,
    ) -> dict[str, object]:
        zone = self._resolve_zone(
            module_code="SHOP",
            preferred_zone_id=merchant.service_zone_id,
            country_code=merchant.country_code,
            city_name=merchant.city_name,
            latitude=delivery_latitude,
            longitude=delivery_longitude,
        )
        profile, source = self._resolve_delivery_profile(
            zone=zone,
            country_code=merchant.country_code,
            partner_metadata_raw=merchant.metadata_json,
            currency=merchant.currency,
        )
        distance_km = self._distance_km(
            merchant.latitude,
            merchant.longitude,
            delivery_latitude,
            delivery_longitude,
        )
        return self._build_delivery_quote(
            module_code="SHOP",
            currency=merchant.currency,
            zone=zone,
            profile=profile,
            source=source,
            distance_km=distance_km,
            requested_delivery_fee=requested_delivery_fee,
        )

    def quote_vtc_ride(
        self,
        *,
        operator: VtcFleetOperator | None,
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
        zone = self._resolve_zone(
            module_code="VTC",
            preferred_zone_id=operator.service_zone_id if operator else None,
            country_code=operator.country_code if operator else None,
            city_name=operator.city_name if operator else None,
            latitude=pickup_latitude,
            longitude=pickup_longitude,
        )
        profile, source = self._resolve_ride_profile(
            zone=zone,
            country_code=operator.country_code if operator else None,
            operator_metadata_raw=operator.metadata_json if operator else None,
            currency=currency,
        )
        inferred_distance = estimated_distance_km
        if inferred_distance is None:
            distance_float = self._distance_km(
                pickup_latitude,
                pickup_longitude,
                destination_latitude,
                destination_longitude,
            )
            inferred_distance = _to_decimal(distance_float, "0") if distance_float is not None else None
        avg_speed_kph = _to_decimal(profile.get("averageSpeedKph"), "28")
        inferred_duration = estimated_duration_minutes
        if inferred_duration is None and inferred_distance is not None and avg_speed_kph > Decimal("0"):
            inferred_duration = max(1, int((inferred_distance / avg_speed_kph * Decimal("60")).quantize(Decimal("1"), rounding=ROUND_HALF_UP)))

        if estimated_fare is not None and estimated_fare > Decimal("0"):
            quoted = _quantize_money(_to_decimal(estimated_fare))
            base_amount = quoted
            distance_amount = Decimal("0")
            time_amount = Decimal("0")
            surge = Decimal("1.0000")
            min_fare = quoted
            manual_override_applied = True
        else:
            base_amount = _quantize_money(_to_decimal(profile.get("baseFare"), "2.50"))
            distance_rate = _to_decimal(profile.get("distanceRatePerKm"), "0.80")
            time_rate = _to_decimal(profile.get("timeRatePerMinute"), "0.12")
            min_fare = _quantize_money(_to_decimal(profile.get("minimumFare"), "2.50"))
            surge = _to_decimal(profile.get("defaultSurgeMultiplier"), "1.0000").quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
            premium_multiplier = _to_decimal(profile.get("premiumMultiplier"), "1.1500")
            standard_multiplier = _to_decimal(profile.get("standardMultiplier"), "1.0000")
            ride_multiplier = premium_multiplier if ride_type == "premium" else standard_multiplier
            distance_amount = _quantize_money(_to_decimal(inferred_distance) * distance_rate)
            time_amount = _quantize_money(_to_decimal(inferred_duration) * time_rate)
            quoted = _quantize_money((base_amount + distance_amount + time_amount) * surge * ride_multiplier)
            if quoted < min_fare:
                quoted = min_fare
            manual_override_applied = False

        platform_fee_rate = _to_decimal(profile.get("platformFeeRate"), "0.20").quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        platform_fee_amount = _quantize_money(quoted * platform_fee_rate)
        driver_payout_amount = _quantize_money(quoted - platform_fee_amount)
        return {
            "moduleCode": "VTC",
            "currency": currency.upper(),
            "zoneId": zone.id if zone else None,
            "zoneCode": zone.code if zone else None,
            "pricingSource": source,
            "rideType": ride_type,
            "estimatedDistanceKm": _quantize_money(_to_decimal(inferred_distance)) if inferred_distance is not None else None,
            "estimatedDurationMinutes": inferred_duration,
            "baseFareAmount": base_amount,
            "distanceFareAmount": distance_amount,
            "timeFareAmount": time_amount,
            "surgeMultiplier": surge,
            "minimumFare": min_fare,
            "quotedFare": quoted,
            "platformFeeRate": platform_fee_rate,
            "platformFeeAmount": platform_fee_amount,
            "driverPayoutAmount": driver_payout_amount,
            "manualOverrideApplied": manual_override_applied,
            "requestedFare": _quantize_money(_to_decimal(estimated_fare)) if estimated_fare is not None else None,
        }

    def serialize_quote(self, payload: dict[str, object]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in payload.items():
            if isinstance(value, Decimal):
                result[key] = str(value)
            elif isinstance(value, dict):
                result[key] = self.serialize_quote(value)
            elif isinstance(value, list):
                result[key] = [self.serialize_quote(item) if isinstance(item, dict) else str(item) if isinstance(item, Decimal) else item for item in value]
            else:
                result[key] = value
        return result

    def _build_delivery_quote(
        self,
        *,
        module_code: str,
        currency: str,
        zone: ServiceZone | None,
        profile: dict[str, object],
        source: str,
        distance_km: float | None,
        requested_delivery_fee: Decimal | None,
    ) -> dict[str, object]:
        base_fee = _quantize_money(_to_decimal(profile.get("baseFee"), "2.00"))
        distance_rate = _to_decimal(profile.get("distanceRatePerKm"), "0.50")
        included_distance_km = _to_decimal(profile.get("includedDistanceKm"), "0")
        minimum_fee = _quantize_money(_to_decimal(profile.get("minimumFee"), "2.00"))
        surge_multiplier = _to_decimal(profile.get("surgeMultiplier"), "1.0000").quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        max_radius_km = _to_decimal(profile.get("maxDeliveryRadiusKm"), "0")

        distance_decimal = _quantize_money(_to_decimal(distance_km)) if distance_km is not None else None
        billable_distance_km = Decimal("0")
        if distance_decimal is not None:
            billable_distance_km = distance_decimal - included_distance_km
            if billable_distance_km < Decimal("0"):
                billable_distance_km = Decimal("0")
            if max_radius_km > Decimal("0") and distance_decimal > max_radius_km:
                raise ValueError("La distance de livraison dÃ©passe le rayon autorisÃ© pour cette zone.")

        distance_amount = _quantize_money(billable_distance_km * distance_rate)
        quoted_fee = _quantize_money((base_fee + distance_amount) * surge_multiplier)
        if quoted_fee < minimum_fee:
            quoted_fee = minimum_fee
        final_fee = _quantize_money(_to_decimal(requested_delivery_fee)) if requested_delivery_fee is not None else quoted_fee
        return {
            "moduleCode": module_code,
            "currency": currency.upper(),
            "zoneId": zone.id if zone else None,
            "zoneCode": zone.code if zone else None,
            "pricingSource": source,
            "distanceKm": distance_decimal,
            "includedDistanceKm": _quantize_money(included_distance_km),
            "billableDistanceKm": _quantize_money(billable_distance_km),
            "baseFee": base_fee,
            "distanceRatePerKm": _quantize_money(distance_rate),
            "distanceAmount": distance_amount,
            "minimumFee": minimum_fee,
            "surgeMultiplier": surge_multiplier,
            "quotedFee": quoted_fee,
            "finalFee": final_fee,
            "manualOverrideApplied": requested_delivery_fee is not None,
            "requestedDeliveryFee": _quantize_money(_to_decimal(requested_delivery_fee)) if requested_delivery_fee is not None else None,
        }

    def _resolve_delivery_profile(
        self,
        *,
        zone: ServiceZone | None,
        country_code: str | None,
        partner_metadata_raw: str | None,
        currency: str,
    ) -> tuple[dict[str, object], str]:
        profile: dict[str, object] = self._resolve_geo_base_profile(
            country_code=country_code,
            currency=currency,
            profile_key="deliveryPricing",
        )
        source = "country_or_continent" if profile else "default"
        zone_payload = self._safe_json_loads(zone.pricing_profile_json if zone else None)
        if isinstance(zone_payload, dict):
            zone_profile = zone_payload.get("deliveryPricing") if isinstance(zone_payload.get("deliveryPricing"), dict) else zone_payload
            if isinstance(zone_profile, dict):
                profile.update(zone_profile)
                source = "service_zone"
        partner_payload = self._safe_json_loads(partner_metadata_raw)
        if isinstance(partner_payload, dict):
            partner_profile = partner_payload.get("deliveryPricing")
            if isinstance(partner_profile, dict):
                profile.update(partner_profile)
                source = "partner_metadata"
        if not profile:
            profile = self._default_delivery_profile(currency)
        else:
            defaults = self._default_delivery_profile(currency)
            defaults.update(profile)
            profile = defaults
        return profile, source

    def _resolve_ride_profile(
        self,
        *,
        zone: ServiceZone | None,
        country_code: str | None,
        operator_metadata_raw: str | None,
        currency: str,
    ) -> tuple[dict[str, object], str]:
        profile: dict[str, object] = self._resolve_geo_base_profile(
            country_code=country_code,
            currency=currency,
            profile_key="ridePricing",
        )
        source = "country_or_continent" if profile else "default"
        zone_payload = self._safe_json_loads(zone.pricing_profile_json if zone else None)
        if isinstance(zone_payload, dict):
            zone_profile = zone_payload.get("ridePricing") if isinstance(zone_payload.get("ridePricing"), dict) else zone_payload.get("pricing")
            if isinstance(zone_profile, dict):
                profile.update(zone_profile)
                source = "service_zone"
        operator_payload = self._safe_json_loads(operator_metadata_raw)
        if isinstance(operator_payload, dict):
            operator_profile = None
            if isinstance(operator_payload.get("ridePricing"), dict):
                operator_profile = operator_payload.get("ridePricing")
            elif isinstance(operator_payload.get("pricing"), dict):
                operator_profile = operator_payload.get("pricing")
            if isinstance(operator_profile, dict):
                profile.update(operator_profile)
                source = "operator_metadata"
        if not profile:
            profile = self._default_ride_profile(currency)
        else:
            defaults = self._default_ride_profile(currency)
            defaults.update(profile)
            profile = defaults
        return profile, source

    def _resolve_zone(
        self,
        *,
        module_code: str,
        preferred_zone_id: str | None,
        country_code: str | None,
        city_name: str | None,
        latitude: float | None,
        longitude: float | None,
    ) -> ServiceZone | None:
        if preferred_zone_id:
            zone = self.db.get(ServiceZone, preferred_zone_id)
            if zone is not None:
                return zone
        stmt = select(ServiceZone).where(
            ServiceZone.module_code == module_code.upper(),
            ServiceZone.is_active.is_(True),
            ServiceZone.launch_status == "ACTIVE",
        )
        if country_code:
            stmt = stmt.where(ServiceZone.code.like(f"{country_code.upper()}-%"))
        candidates = self.db.execute(stmt).scalars().all()
        if not candidates:
            return None
        if city_name:
            city_prefix = city_name.strip().replace(" ", "_").upper()
            city_matches = [zone for zone in candidates if city_prefix in zone.code]
            if city_matches:
                candidates = city_matches
        if latitude is None or longitude is None:
            return candidates[0]
        containing = [zone for zone in candidates if self._zone_contains_point(zone, latitude, longitude)]
        if containing:
            return containing[0]
        return candidates[0]

    def _resolve_geo_base_profile(
        self,
        *,
        country_code: str | None,
        currency: str,
        profile_key: str,
    ) -> dict[str, object]:
        country = None
        if country_code:
            normalized = country_code.strip().upper()
            country = self.db.execute(select(Country).where(Country.iso_code == normalized)).scalars().one_or_none()
            if country is None:
                country = self.db.execute(select(Country).where(Country.name == normalized)).scalars().one_or_none()

        profile: dict[str, object] = {}
        continent = None
        if country and country.continent_code:
            continent = self.db.execute(select(Continent).where(Continent.code == country.continent_code)).scalars().one_or_none()

        if continent and continent.pricing_profile_json:
            continent_payload = self._safe_json_loads(continent.pricing_profile_json)
            if isinstance(continent_payload, dict):
                continent_profile = continent_payload.get(profile_key) if isinstance(continent_payload.get(profile_key), dict) else continent_payload
                if isinstance(continent_profile, dict):
                    profile.update(continent_profile)

        if country and country.pricing_profile_json:
            country_payload = self._safe_json_loads(country.pricing_profile_json)
            if isinstance(country_payload, dict):
                country_profile = country_payload.get(profile_key) if isinstance(country_payload.get(profile_key), dict) else country_payload
                if isinstance(country_profile, dict):
                    profile.update(country_profile)

        if not profile:
            return {}
        defaults = self._default_ride_profile(currency) if profile_key == "ridePricing" else self._default_delivery_profile(currency)
        defaults.update(profile)
        return defaults

    def _zone_contains_point(self, zone: ServiceZone, latitude: float, longitude: float) -> bool:
        polygon = self._extract_polygon_points(zone.coverage_json)
        if polygon:
            return self._point_in_polygon(latitude, longitude, polygon)
        if zone.center_latitude is not None and zone.center_longitude is not None and zone.radius_km is not None:
            distance = self._distance_km(latitude, longitude, zone.center_latitude, zone.center_longitude)
            return distance is not None and distance <= float(zone.radius_km)
        return True

    def _default_delivery_profile(self, currency: str) -> dict[str, object]:
        code = currency.upper()
        defaults = {
            "XOF": {"baseFee": "500", "distanceRatePerKm": "150", "minimumFee": "500", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "GHS": {"baseFee": "4", "distanceRatePerKm": "1.20", "minimumFee": "4", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "NGN": {"baseFee": "900", "distanceRatePerKm": "220", "minimumFee": "900", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "EUR": {"baseFee": "2.50", "distanceRatePerKm": "0.90", "minimumFee": "2.50", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "USD": {"baseFee": "3.00", "distanceRatePerKm": "1.00", "minimumFee": "3.00", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "GBP": {"baseFee": "2.80", "distanceRatePerKm": "0.95", "minimumFee": "2.80", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
            "CAD": {"baseFee": "3.50", "distanceRatePerKm": "1.20", "minimumFee": "3.50", "includedDistanceKm": "0", "surgeMultiplier": "1.0000", "maxDeliveryRadiusKm": "20"},
        }
        return defaults.get(code, defaults["EUR"]).copy()

    def _default_ride_profile(self, currency: str) -> dict[str, object]:
        code = currency.upper()
        defaults = {
            "XOF": {"baseFare": "1000", "distanceRatePerKm": "250", "timeRatePerMinute": "45", "minimumFare": "1000", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "GHS": {"baseFare": "6", "distanceRatePerKm": "1.60", "timeRatePerMinute": "0.35", "minimumFare": "6", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "NGN": {"baseFare": "1200", "distanceRatePerKm": "260", "timeRatePerMinute": "55", "minimumFare": "1200", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "EUR": {"baseFare": "2.50", "distanceRatePerKm": "0.80", "timeRatePerMinute": "0.12", "minimumFare": "2.50", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "USD": {"baseFare": "3.00", "distanceRatePerKm": "1.00", "timeRatePerMinute": "0.18", "minimumFare": "3.00", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "GBP": {"baseFare": "2.80", "distanceRatePerKm": "0.95", "timeRatePerMinute": "0.16", "minimumFare": "2.80", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
            "CAD": {"baseFare": "3.50", "distanceRatePerKm": "1.20", "timeRatePerMinute": "0.20", "minimumFare": "3.50", "defaultSurgeMultiplier": "1.0000", "platformFeeRate": "0.20", "premiumMultiplier": "1.1500", "averageSpeedKph": "28"},
        }
        return defaults.get(code, defaults["EUR"]).copy()

    def _safe_json_loads(self, raw: str | None) -> dict | list | None:
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            return None

    @staticmethod
    def _extract_polygon_points(raw: str | None) -> list[tuple[float, float]]:
        if not raw:
            return []
        try:
            payload = json.loads(raw)
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
    def _distance_km(
        lat1: float | None,
        lon1: float | None,
        lat2: float | None,
        lon2: float | None,
    ) -> float | None:
        if None in {lat1, lon1, lat2, lon2}:
            return None
        radius = 6371.0
        phi1 = math.radians(float(lat1))
        phi2 = math.radians(float(lat2))
        d_phi = math.radians(float(lat2) - float(lat1))
        d_lambda = math.radians(float(lon2) - float(lon1))
        a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return radius * c
