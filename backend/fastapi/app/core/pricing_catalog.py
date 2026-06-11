from __future__ import annotations

from copy import deepcopy


CONTINENT_PRICING_PROFILES: dict[str, dict[str, dict[str, str]]] = {
    "AF": {
        "ridePricing": {
            "baseFare": "1000",
            "distanceRatePerKm": "240",
            "timeRatePerMinute": "45",
            "minimumFare": "1000",
            "defaultSurgeMultiplier": "1.0000",
            "platformFeeRate": "0.20",
            "premiumMultiplier": "1.1500",
            "averageSpeedKph": "26",
        },
        "deliveryPricing": {
            "baseFee": "500",
            "distanceRatePerKm": "150",
            "includedDistanceKm": "0",
            "minimumFee": "500",
            "surgeMultiplier": "1.0000",
            "maxDeliveryRadiusKm": "15",
        },
    },
    "EU": {
        "ridePricing": {
            "baseFare": "3.00",
            "distanceRatePerKm": "1.10",
            "timeRatePerMinute": "0.20",
            "minimumFare": "3.00",
            "defaultSurgeMultiplier": "1.0000",
            "platformFeeRate": "0.20",
            "premiumMultiplier": "1.1500",
            "averageSpeedKph": "30",
        },
        "deliveryPricing": {
            "baseFee": "2.90",
            "distanceRatePerKm": "0.95",
            "includedDistanceKm": "0",
            "minimumFee": "2.90",
            "surgeMultiplier": "1.0000",
            "maxDeliveryRadiusKm": "18",
        },
    },
    "NA": {
        "ridePricing": {
            "baseFare": "3.50",
            "distanceRatePerKm": "1.25",
            "timeRatePerMinute": "0.24",
            "minimumFare": "3.50",
            "defaultSurgeMultiplier": "1.0000",
            "platformFeeRate": "0.20",
            "premiumMultiplier": "1.1500",
            "averageSpeedKph": "32",
        },
        "deliveryPricing": {
            "baseFee": "3.50",
            "distanceRatePerKm": "1.20",
            "includedDistanceKm": "0",
            "minimumFee": "3.50",
            "surgeMultiplier": "1.0000",
            "maxDeliveryRadiusKm": "20",
        },
    },
    "OTHER": {
        "ridePricing": {
            "baseFare": "3.00",
            "distanceRatePerKm": "1.00",
            "timeRatePerMinute": "0.18",
            "minimumFare": "3.00",
            "defaultSurgeMultiplier": "1.0000",
            "platformFeeRate": "0.20",
            "premiumMultiplier": "1.1500",
            "averageSpeedKph": "28",
        },
        "deliveryPricing": {
            "baseFee": "3.00",
            "distanceRatePerKm": "1.00",
            "includedDistanceKm": "0",
            "minimumFee": "3.00",
            "surgeMultiplier": "1.0000",
            "maxDeliveryRadiusKm": "20",
        },
    },
}


COUNTRY_PRICING_PROFILES: dict[str, dict[str, dict[str, str]]] = {
    "TG": {
        "ridePricing": {
            "baseFare": "1000",
            "distanceRatePerKm": "250",
            "timeRatePerMinute": "45",
            "minimumFare": "1000",
            "averageSpeedKph": "24",
        },
        "deliveryPricing": {
            "baseFee": "500",
            "distanceRatePerKm": "150",
            "minimumFee": "500",
            "maxDeliveryRadiusKm": "12",
        },
    },
    "BJ": {
        "ridePricing": {
            "baseFare": "1000",
            "distanceRatePerKm": "240",
            "timeRatePerMinute": "42",
            "minimumFare": "1000",
            "averageSpeedKph": "24",
        },
        "deliveryPricing": {
            "baseFee": "500",
            "distanceRatePerKm": "145",
            "minimumFee": "500",
            "maxDeliveryRadiusKm": "12",
        },
    },
    "GH": {
        "ridePricing": {
            "baseFare": "6",
            "distanceRatePerKm": "1.60",
            "timeRatePerMinute": "0.35",
            "minimumFare": "6",
            "averageSpeedKph": "26",
        },
        "deliveryPricing": {
            "baseFee": "4",
            "distanceRatePerKm": "1.20",
            "minimumFee": "4",
            "maxDeliveryRadiusKm": "14",
        },
    },
    "NG": {
        "ridePricing": {
            "baseFare": "1200",
            "distanceRatePerKm": "260",
            "timeRatePerMinute": "55",
            "minimumFare": "1200",
            "averageSpeedKph": "23",
        },
        "deliveryPricing": {
            "baseFee": "900",
            "distanceRatePerKm": "220",
            "minimumFee": "900",
            "maxDeliveryRadiusKm": "14",
        },
    },
    "CI": {
        "ridePricing": {
            "baseFare": "1100",
            "distanceRatePerKm": "255",
            "timeRatePerMinute": "48",
            "minimumFare": "1100",
            "averageSpeedKph": "24",
        },
        "deliveryPricing": {
            "baseFee": "600",
            "distanceRatePerKm": "160",
            "minimumFee": "600",
            "maxDeliveryRadiusKm": "13",
        },
    },
    "SN": {
        "ridePricing": {
            "baseFare": "1200",
            "distanceRatePerKm": "260",
            "timeRatePerMinute": "50",
            "minimumFare": "1200",
            "averageSpeedKph": "25",
        },
        "deliveryPricing": {
            "baseFee": "650",
            "distanceRatePerKm": "170",
            "minimumFee": "650",
            "maxDeliveryRadiusKm": "14",
        },
    },
    "FR": {
        "ridePricing": {
            "baseFare": "3.50",
            "distanceRatePerKm": "1.25",
            "timeRatePerMinute": "0.28",
            "minimumFare": "3.50",
            "averageSpeedKph": "28",
        },
        "deliveryPricing": {
            "baseFee": "3.20",
            "distanceRatePerKm": "1.05",
            "minimumFee": "3.20",
            "maxDeliveryRadiusKm": "16",
        },
    },
    "ES": {
        "ridePricing": {
            "baseFare": "3.20",
            "distanceRatePerKm": "1.05",
            "timeRatePerMinute": "0.22",
            "minimumFare": "3.20",
            "averageSpeedKph": "30",
        },
        "deliveryPricing": {
            "baseFee": "3.00",
            "distanceRatePerKm": "0.95",
            "minimumFee": "3.00",
            "maxDeliveryRadiusKm": "16",
        },
    },
    "EE": {
        "ridePricing": {
            "baseFare": "2.80",
            "distanceRatePerKm": "0.90",
            "timeRatePerMinute": "0.18",
            "minimumFare": "2.80",
            "averageSpeedKph": "32",
        },
        "deliveryPricing": {
            "baseFee": "2.80",
            "distanceRatePerKm": "0.90",
            "minimumFee": "2.80",
            "maxDeliveryRadiusKm": "15",
        },
    },
    "US": {
        "ridePricing": {
            "baseFare": "3.80",
            "distanceRatePerKm": "1.30",
            "timeRatePerMinute": "0.26",
            "minimumFare": "3.80",
            "averageSpeedKph": "32",
        },
        "deliveryPricing": {
            "baseFee": "3.75",
            "distanceRatePerKm": "1.25",
            "minimumFee": "3.75",
            "maxDeliveryRadiusKm": "20",
        },
    },
    "GB": {
        "ridePricing": {
            "baseFare": "3.10",
            "distanceRatePerKm": "1.05",
            "timeRatePerMinute": "0.21",
            "minimumFare": "3.10",
            "averageSpeedKph": "29",
        },
        "deliveryPricing": {
            "baseFee": "3.00",
            "distanceRatePerKm": "1.00",
            "minimumFee": "3.00",
            "maxDeliveryRadiusKm": "18",
        },
    },
    "CA": {
        "ridePricing": {
            "baseFare": "3.60",
            "distanceRatePerKm": "1.20",
            "timeRatePerMinute": "0.22",
            "minimumFare": "3.60",
            "averageSpeedKph": "31",
        },
        "deliveryPricing": {
            "baseFee": "3.50",
            "distanceRatePerKm": "1.20",
            "minimumFee": "3.50",
            "maxDeliveryRadiusKm": "20",
        },
    },
}


def build_continent_pricing_profile(continent_code: str) -> dict[str, dict[str, str]]:
    code = (continent_code or "OTHER").strip().upper()
    base = CONTINENT_PRICING_PROFILES.get(code) or CONTINENT_PRICING_PROFILES["OTHER"]
    return deepcopy(base)


def build_country_pricing_profile(country_code: str, continent_code: str | None = None) -> dict[str, dict[str, str]]:
    continent_profile = build_continent_pricing_profile(continent_code or "OTHER")
    country = (country_code or "").strip().upper()
    override = COUNTRY_PRICING_PROFILES.get(country)
    if not override:
        return continent_profile
    result = deepcopy(continent_profile)
    for key, payload in override.items():
        result.setdefault(key, {})
        result[key].update(payload)
    return result

