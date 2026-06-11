# ZASKA Initial Pricing Matrix

## Goal

This file contains the recommended initial backend pricing values to use as launch defaults before market-by-market fine tuning.

These values are:

- initial
- adjustable by admin
- not hard-locked
- intended as a strong operational starting point

---

## Resolution Logic

The backend resolves pricing in this order:

1. manual override
2. partner/operator override
3. service zone pricing
4. country pricing
5. continent pricing
6. backend currency default

---

## Continent Defaults

## Africa (`AF`)

### VTC

- base fare: `1000`
- distance per km: `240`
- time per minute: `45`
- minimum fare: `1000`
- surge: `1.0000`
- platform fee: `20%`
- premium multiplier: `1.1500`

### Delivery

- base fee: `500`
- distance per km: `150`
- minimum fee: `500`
- max radius: `15 km`

## Europe (`EU`)

### VTC

- base fare: `3.00`
- distance per km: `1.10`
- time per minute: `0.20`
- minimum fare: `3.00`
- surge: `1.0000`
- platform fee: `20%`
- premium multiplier: `1.1500`

### Delivery

- base fee: `2.90`
- distance per km: `0.95`
- minimum fee: `2.90`
- max radius: `18 km`

## North America (`NA`)

### VTC

- base fare: `3.50`
- distance per km: `1.25`
- time per minute: `0.24`
- minimum fare: `3.50`

### Delivery

- base fee: `3.50`
- distance per km: `1.20`
- minimum fee: `3.50`
- max radius: `20 km`

---

## Country Launch Profiles

## Togo (`TG`)

- VTC: base `1000`, km `250`, minute `45`, min `1000`
- Delivery: base `500`, km `150`, min `500`, radius `12 km`

## Benin (`BJ`)

- VTC: base `1000`, km `240`, minute `42`, min `1000`
- Delivery: base `500`, km `145`, min `500`, radius `12 km`

## Ghana (`GH`)

- VTC: base `6`, km `1.60`, minute `0.35`, min `6`
- Delivery: base `4`, km `1.20`, min `4`, radius `14 km`

## Nigeria (`NG`)

- VTC: base `1200`, km `260`, minute `55`, min `1200`
- Delivery: base `900`, km `220`, min `900`, radius `14 km`

## Côte d’Ivoire (`CI`)

- VTC: base `1100`, km `255`, minute `48`, min `1100`
- Delivery: base `600`, km `160`, min `600`, radius `13 km`

## Sénégal (`SN`)

- VTC: base `1200`, km `260`, minute `50`, min `1200`
- Delivery: base `650`, km `170`, min `650`, radius `14 km`

## France (`FR`)

- VTC: base `3.50`, km `1.25`, minute `0.28`, min `3.50`
- Delivery: base `3.20`, km `1.05`, min `3.20`, radius `16 km`

## Spain (`ES`)

- VTC: base `3.20`, km `1.05`, minute `0.22`, min `3.20`
- Delivery: base `3.00`, km `0.95`, min `3.00`, radius `16 km`

## Estonia (`EE`)

- VTC: base `2.80`, km `0.90`, minute `0.18`, min `2.80`
- Delivery: base `2.80`, km `0.90`, min `2.80`, radius `15 km`

---

## Diaspora / Additional Profiles

## United States (`US`)

- VTC: base `3.80`, km `1.30`, minute `0.26`, min `3.80`
- Delivery: base `3.75`, km `1.25`, min `3.75`, radius `20 km`

## United Kingdom (`GB`)

- VTC: base `3.10`, km `1.05`, minute `0.21`, min `3.10`
- Delivery: base `3.00`, km `1.00`, min `3.00`, radius `18 km`

## Canada (`CA`)

- VTC: base `3.60`, km `1.20`, minute `0.22`, min `3.60`
- Delivery: base `3.50`, km `1.20`, min `3.50`, radius `20 km`

---

## Backend Assets Added

- pricing catalog:
  - `backend/fastapi/app/core/pricing_catalog.py`
- pricing seed:
  - `backend/fastapi/scripts/seed_pricing_profiles.py`
- admin pricing template endpoints:
  - `GET /admin/pricing/templates/continents/{continent_code}`
  - `GET /admin/pricing/templates/countries/{country_code}`

---

## Recommended Admin Workflow

1. load continent template
2. load country template
3. review values with operations/finance
4. save country pricing
5. create zone overrides only where needed

---

## Important Note

These are **starting values**, not immutable truth.

The purpose is to:

- avoid launching with no market logic
- keep pricing coherent from day one
- enable country-specific control from the admin interface later

