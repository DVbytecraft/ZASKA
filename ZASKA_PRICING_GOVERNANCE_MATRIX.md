# ZASKA Pricing Governance Matrix

## Objective

Define how pricing is governed across:

- continent
- country
- city / service zone
- operator / restaurant / merchant

This is the intended hierarchy for:

- VTC base fares
- FOOD delivery base fees
- SHOP delivery base fees

---

## Governance Hierarchy

### Resolution order

The backend now resolves pricing in this order:

1. request manual override
2. operator / restaurant / merchant metadata override
3. service zone pricing profile
4. country pricing profile
5. continent pricing profile
6. backend currency default

This allows:

- global safety defaults
- regional defaults
- country-level market tuning
- zone-level operational tuning
- partner-level negotiated exceptions

---

## Admin-Controlled Pricing Levels

### 1. Continent level

Use this as a broad fallback when no country-specific profile exists yet.

### 2. Country level

This should be the main pricing level for launch.

### 3. Service zone level

Use this for real operational precision:

- dense city centers
- airport zones
- high-traffic districts
- difficult delivery areas

### 4. Partner/operator override

Use only when commercially justified:

- premium fleet operator
- high-end restaurant chain
- special merchant contract

---

## Data Structure

## Continent / Country pricing profile shape

The pricing profile JSON can contain:

```json
{
  "ridePricing": {
    "baseFare": "2.50",
    "distanceRatePerKm": "0.80",
    "timeRatePerMinute": "0.12",
    "minimumFare": "2.50",
    "defaultSurgeMultiplier": "1.0000",
    "platformFeeRate": "0.20",
    "premiumMultiplier": "1.1500",
    "averageSpeedKph": "28"
  },
  "deliveryPricing": {
    "baseFee": "2.00",
    "distanceRatePerKm": "0.50",
    "includedDistanceKm": "0",
    "minimumFee": "2.00",
    "surgeMultiplier": "1.0000",
    "maxDeliveryRadiusKm": "20"
  }
}
```

---

## Recommended Use by Module

## VTC

At minimum define:

- `baseFare`
- `distanceRatePerKm`
- `timeRatePerMinute`
- `minimumFare`
- `defaultSurgeMultiplier`
- `platformFeeRate`
- `premiumMultiplier`

## FOOD delivery

At minimum define:

- `baseFee`
- `distanceRatePerKm`
- `includedDistanceKm`
- `minimumFee`
- `surgeMultiplier`
- `maxDeliveryRadiusKm`

## SHOP delivery

Uses the same `deliveryPricing` structure as FOOD.

---

## Admin Backend Endpoints

### Continent pricing

- `PUT /admin/geo/continents/{continent_code}/pricing`

Payload:

```json
{
  "pricing_profile": {
    "ridePricing": {
      "baseFare": "2.80",
      "distanceRatePerKm": "0.95",
      "timeRatePerMinute": "0.16",
      "minimumFare": "2.80",
      "defaultSurgeMultiplier": "1.0000",
      "platformFeeRate": "0.20",
      "premiumMultiplier": "1.1500"
    },
    "deliveryPricing": {
      "baseFee": "2.50",
      "distanceRatePerKm": "0.90",
      "includedDistanceKm": "0",
      "minimumFee": "2.50",
      "surgeMultiplier": "1.0000",
      "maxDeliveryRadiusKm": "20"
    }
  }
}
```

### Country pricing

- `PUT /admin/geo/countries/{country_code}/pricing`

Payload:

```json
{
  "pricing_profile": {
    "ridePricing": {
      "baseFare": "1000",
      "distanceRatePerKm": "250",
      "timeRatePerMinute": "45",
      "minimumFare": "1000",
      "defaultSurgeMultiplier": "1.0000",
      "platformFeeRate": "0.20",
      "premiumMultiplier": "1.1500"
    },
    "deliveryPricing": {
      "baseFee": "500",
      "distanceRatePerKm": "150",
      "includedDistanceKm": "0",
      "minimumFee": "500",
      "surgeMultiplier": "1.0000",
      "maxDeliveryRadiusKm": "20"
    }
  }
}
```

### Service zone pricing

Already supported through:

- `PUT /admin/geo/service-zones`

with:

- `pricing_profile`

---

## What the Future Admin Interface Should Expose

For each selected continent or country:

- module tabs:
  - `VTC`
  - `FOOD`
  - `SHOP`

- fields for `VTC`
  - base fare
  - per km
  - per minute
  - minimum fare
  - surge multiplier
  - platform fee
  - premium multiplier

- fields for `Delivery`
  - base fee
  - per km
  - included distance
  - minimum fee
  - surge multiplier
  - max delivery radius

- actions
  - save draft
  - publish pricing
  - clone from continent
  - clone from country

---

## Recommended Operational Policy

### Continent

Use for:

- startup fallback
- new countries not yet finely calibrated

### Country

Use for:

- official launch pricing
- real market ownership

### Zone

Use for:

- dense city adjustment
- airport logic
- hard-to-serve delivery radius

### Partner override

Use sparingly:

- premium operators
- strategic food chains
- contract merchants

---

## Backend Status

### Now implemented

- pricing fallback from continent
- pricing override by country
- pricing override by service zone
- pricing override by partner/operator metadata
- admin endpoints for continent pricing
- admin endpoints for country pricing

### Still to expose in frontend later

- admin forms
- pricing tables UI
- pricing history UI
- compare / clone actions

