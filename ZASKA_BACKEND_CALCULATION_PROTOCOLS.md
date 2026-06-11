# ZASKA Backend Calculation Protocols

## Purpose

This document centralizes the backend calculation rules already implemented in the repository, the override points exposed to admin configuration, and the remaining calibration work required before final market launch.

It is the reference file for:

- product pricing logic
- social split logic
- wallet and escrow flows
- subscription consumption logic
- referral reward triggering
- AML / dispute financial holds
- remaining backend pricing calibration

---

## Global Status

### Structurally implemented in backend

- Social split for task completion
- General task price negotiation / counter-proposals
- VTC quote and payout calculation
- FOOD delivery quote and payout calculation
- SHOP delivery quote and payout calculation
- Escrow funding / release / refund flows
- Partial completion financial logic
- Subscription quota deduction
- Referral trigger conditions
- AML pre-release blocking
- Dispute frozen-audit flows

### Still requiring business calibration

- final market values by country / city / zone
- launch thresholds for surge usage
- final minimum fares by module
- exceptional pricing rules by service zone
- commercial ceilings / floors by market

---

## Configuration Sources

### Runtime calculation sources already supported

1. `service_zones.pricing_profile_json`
2. partner / operator `metadata_json`
3. backend defaults by currency

### Override hierarchy

The pricing engine currently resolves values in this order:

1. explicit manual override passed in request
2. partner/operator metadata override
3. service zone pricing profile
4. backend currency default

This makes the backend flexible without forcing code edits for every market.

---

## 1. General Task Pricing

### Current behavior

General tasks keep a free price model with negotiation support.

### Backend support

- task creation with initial requested price
- tasker proposal / application
- counter-proposal workflow
- acceptance / refusal flow
- negotiated price persistence

### Main rule

- client can publish a price
- tasker can accept or negotiate
- final task financial flow uses the accepted/negotiated amount

### Current status

- implemented
- ready for frontend exposure

### Remaining calibration

- optional minimum price by category
- optional anti-dumping thresholds by country
- optional category-based recommended price ranges

---

## 2. Social Split After Task Completion

### Current implemented split

On validated task completion:

- `77.5%` → tasker
- `8%` → Zaska operational account
- `7%` → pension fund
- `5%` → health fund
- `2.5%` → smoothing fund

### Trigger

- customer OTP validation
- or automatic release after timeout according to task/service rules

### Current status

- implemented in backend
- transaction history and split visibility already supported

### Remaining verification

- final end-to-end live validation on deployed environment
- accounting reconciliation against live ledgers

---

## 3. Partial Completion / Abandonment Logic

### Current behavior

When a tasker abandons after partial completion:

- proportional tasker payment is calculated
- client receives the remaining refund
- escrow is partially released/refunded

### Current status

- implemented

### Remaining calibration

- business communication wording by market
- optional admin rules per category

---

## 4. VTC Calculation Protocol

## Formula

The VTC quote protocol currently supports:

- base fare
- distance charge
- time charge
- surge multiplier
- minimum fare
- ride type multiplier
- platform fee
- driver payout

### Formula shape

`quoted fare = max(minimum fare, (base fare + distance amount + time amount) * surge * ride type multiplier)`

Then:

- `platform fee amount = quoted fare * platform fee rate`
- `driver payout amount = quoted fare - platform fee amount`

### Inputs

- pickup latitude / longitude
- destination latitude / longitude
- estimated distance
- estimated duration
- ride type
- optional manual fare override

### Supported breakdown

- base fare
- distance fare amount
- time fare amount
- surge multiplier
- quoted fare
- platform fee amount
- driver payout amount

### Backend source

- service zone pricing
- operator pricing metadata
- backend defaults by currency

### Current status

- implemented
- quote endpoint available
- ride response exposes breakdown

### Remaining calibration

- final operator-by-operator tariffs
- premium multiplier policy
- surge activation policy
- airport / toll / waiting-time add-ons if desired

---

## 5. FOOD Delivery Calculation Protocol

## Formula

The FOOD delivery quote protocol currently supports:

- delivery base fee
- included distance
- billable distance
- price per km
- minimum delivery fee
- surge multiplier
- final delivery fee

### Formula shape

`billable distance = max(0, distance - included distance)`

`quoted delivery fee = max(minimum fee, (base fee + billable distance * distance rate) * surge)`

If a manual override is passed, it is preserved as final fee while the calculated breakdown remains available.

### Inputs

- restaurant location
- delivery latitude / longitude
- service zone pricing profile
- optional manual override

### Supported controls

- zone containment
- radius limits
- polygonal service areas
- restaurant opening constraints

### Supported breakdown

- distance km
- included distance km
- billable distance km
- base fee
- distance rate per km
- distance amount
- minimum fee
- surge multiplier
- quoted fee
- final fee

### Current status

- implemented
- quote endpoint available
- order metadata stores pricing breakdown
- order API exposes pricing breakdown

### Remaining calibration

- city-by-city delivery fee tables
- peak hour multiplier policy
- rainy-weather / event multipliers if desired
- minimum basket logic if desired

---

## 6. SHOP Delivery Calculation Protocol

## Formula

SHOP delivery currently follows the same quote model as FOOD delivery:

- base fee
- included distance
- billable distance
- price per km
- minimum fee
- surge multiplier

### Formula shape

`billable distance = max(0, distance - included distance)`

`quoted delivery fee = max(minimum fee, (base fee + billable distance * distance rate) * surge)`

### Current status

- implemented
- quote endpoint available
- order metadata stores pricing breakdown
- order API exposes pricing breakdown

### Remaining calibration

- category-specific heavy-item fee rules
- fragile-item surcharge if desired
- oversized package pricing
- multi-package logistics pricing

---

## 7. Subscription Calculation Protocol

### Current behavior

Subscriptions currently support:

- general Zaska Pro
- service-specific subscriptions
- quota deduction on eligible order/task creation

### Current implemented rules

- verify active subscription
- check remaining quota
- consume quota when applicable
- normal pricing applies when quota exhausted

### Current status

- backend implemented

### Remaining calibration

- final monthly prices
- final included quotas by market
- final savings presentation in frontend
- renewal billing settlement strategy

---

## 8. Referral Calculation Protocol

### Tasker referral

Reward triggers when referred tasker completes first threshold of jobs.

### Client referral

Reward triggers when referred client completes first eligible order.

### Current status

- implemented

### Remaining calibration

- reward amount by market
- wallet reward vs platform credit split
- anti-abuse thresholds

---

## 9. AML / Dispute Financial Protocols

### AML

Current financial protections:

- pre-release AML screening
- threshold-based review
- suspicious repetition detection
- temporary release blocking

### Disputes

Current financial protections:

- frozen audit state
- admin decision release / refund / partial refund
- immutable dispute event trail

### Current status

- implemented

### Remaining calibration

- legal reporting thresholds per market
- operational SLA tuning
- review staffing policy

---

## 10. Admin Override Model

### Already supported by backend

Admin pricing can conceptually be driven through:

- service zones
- partner metadata
- operator metadata

### What this means

The backend is already ready for:

- per country pricing
- per city pricing
- per zone pricing
- per module pricing
- per operator / merchant / restaurant overrides

### What should be exposed in frontend/admin later

- base fare
- base delivery fee
- distance rate
- time rate
- minimum fee
- included distance
- surge multiplier
- platform fee rate
- premium multiplier
- max delivery radius

---

## 11. Recommended Launch Pricing Governance

### Best practice

Do not launch with one global tariff.

### Recommended governance

Set pricing at:

1. country level default
2. city level refinement
3. service zone override
4. operator/partner override only when justified

### Product recommendation

- VTC should always keep:
  - base fare
  - per km
  - per minute
  - minimum fare

- FOOD and SHOP should always keep:
  - base delivery fee
  - per km
  - minimum delivery fee

---

## 12. What Is Ready vs What Is Not Fully Final Yet

### Ready in backend logic

- calculation protocols
- quote generation
- persisted breakdowns
- payout math
- override hierarchy

### Not fully final yet

- final market tariff tables
- live deployed parity validation everywhere
- frontend presentation of every breakdown
- full business sign-off on every market value

---

## 13. Immediate Next Backend Review Recommended

Before locking pricing as “final” market-ready, review and validate:

1. VTC base fare by country/city
2. VTC per-km and per-minute values
3. VTC premium multiplier
4. FOOD delivery base fee by zone
5. FOOD per-km fee by zone
6. SHOP delivery base fee by zone
7. SHOP per-km fee by zone
8. minimum fee by module
9. allowed surge policy by module
10. platform fee policy by module

---

## 14. Reference Files

- `backend/fastapi/app/services/pricing_engine_service.py`
- `backend/fastapi/app/services/vtc_service.py`
- `backend/fastapi/app/services/food_service.py`
- `backend/fastapi/app/services/shop_service.py`
- `backend/fastapi/app/api/v1/routers/vtc.py`
- `backend/fastapi/app/api/v1/routers/food.py`
- `backend/fastapi/app/api/v1/routers/shop.py`
- `backend/fastapi/app/api/v1/routers/tasks.py`
- `backend/fastapi/app/services/wallet_service.py`
- `backend/fastapi/app/services/subscription_service.py`
- `backend/fastapi/app/services/referral_service.py`
- `backend/fastapi/app/services/aml_service.py`
- `backend/fastapi/app/services/dispute_service.py`

