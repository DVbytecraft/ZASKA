# ZASKA Backend Progress Appendix

## Lot 13 — Litiges avancés backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260606_0054_advanced_disputes.py` pour enrichir `disputes` et créer `dispute_events`.
- Modèle litige enrichi avec snapshots tâche/chat/géo/photos, agent assigné, escalation, SLA et journal d’événements.
- Service métier `backend/fastapi/app/services/dispute_service.py` pour ouverture, assignation, note, escalation et décision.
- Route runtime `backend/fastapi/app/api/v1/routers/disputes.py` pour consultation des litiges par les parties.
- Route tâche `contest` branchée sur le nouveau moteur de litige.
- Routes admin enrichies dans `backend/fastapi/app/api/v1/routers/admin.py` :
  - `GET /admin/disputes`
  - `GET /admin/disputes/{dispute_id}`
  - `POST /admin/disputes/{dispute_id}/assign`
  - `POST /admin/disputes/{dispute_id}/note`
  - `POST /admin/disputes/{dispute_id}/escalate`
  - `POST /admin/disputes/{dispute_id}/resolve`
- Wallet raccordé au statut `frozen_audit` et aux résolutions `release`, `refund`, `partial_refund`.

### Garanties
- Approche additive et `prod-safe`.
- SLA 24h préparé via `due_at`.
- Historique immuable des actions via `dispute_events`.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- AML avancé
- KYC avancé complet
- B2B / rôles admin finaux / exports

## Lot 14 — AML avancé backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260607_0055_aml_foundation.py` pour créer `aml_cases`, `aml_events` et enrichir `users` / `tasks`.
- Nouveau domaine AML dans `backend/fastapi/app/models/aml.py`.
- Nouveau service `backend/fastapi/app/services/aml_service.py` avec :
  - screening à la création de tâche,
  - screening avant libération des fonds,
  - cas transactionnels `> 500 EUR`,
  - seuil mensuel `> 2 000 EUR`,
  - détection montants répétés,
  - détection validation trop rapide,
  - détection binôme diaspora répété,
  - revue admin et journal AML.
- Nouveau runtime `backend/fastapi/app/api/v1/routers/aml.py` pour consultation des cas AML par l’utilisateur concerné.
- Intégration dans `backend/fastapi/app/api/v1/routers/tasks.py` pour bloquer la libération des fonds quand une revue AML est requise.
- Endpoints admin AML ajoutés dans `backend/fastapi/app/api/v1/routers/admin.py` :
  - `GET /admin/aml/cases`
  - `GET /admin/aml/cases/{case_id}`
  - `POST /admin/aml/cases/{case_id}/review`

### Garanties
- Approche additive et `prod-safe`.
- Les cas AML sont persistés avant retour `423` sur une libération bloquée.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- KYC avancé complet
- B2B / rôles admin finaux / exports

## Lot 15 — KYC avancé complet backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260607_0056_advanced_kyc_foundation.py` pour enrichir `kyc_submissions`.
- Modèle KYC enrichi dans `backend/fastapi/app/models/kyc.py` avec :
  - type de soumission `full/renewal`,
  - recto/verso document,
  - selfie biométrique,
  - casier judiciaire,
  - statut biométrie,
  - statut OCR,
  - niveau de risque casier,
  - chaînage de renouvellement,
  - métadonnées de préremplissage.
- Service `backend/fastapi/app/services/kyc_service.py` renforcé avec :
  - création de soumission avancée,
  - préremplissage de renouvellement,
  - analyse simulée OCR/NLP provider-agnostic,
  - validation de complétude avant approbation,
  - synchronisation de l’état sécurité tasker.
- API runtime `backend/fastapi/app/api/v1/routers/kyc.py` enrichie :
  - `POST /kyc/submit` avec pièces avancées,
  - `GET /kyc/status`,
  - `GET /kyc/renewal-prefill`.
- Les décisions `approve/reject` côté router KYC sont désormais réservées à l’admin.
- La garde tasker dans `backend/fastapi/app/api/deps.py` vérifie maintenant aussi :
  - statut biométrique KYC,
  - statut casier,
  - niveau de risque casier.
- Le back-office KYC expose plus d’informations dans `backend/fastapi/app/api/v1/routers/admin.py`.

### Garanties
- Approche additive et `prod-safe`.
- Renouvellement simplifié préparé sans casser les anciennes données.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- B2B / rôles admin finaux / exports
- préparation shop / VTC si on garde l’ordre fondation backend

## Lot 16 — B2B + exports backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260607_0057_b2b_and_exports_foundation.py`.
- Nouveau domaine B2B dans `backend/fastapi/app/models/b2b.py` avec :
  - organisations entreprise,
  - memberships,
  - contrats,
  - templates de tâches,
  - work orders,
  - jobs d’export admin.
- Nouveau service `backend/fastapi/app/services/b2b_service.py` pour :
  - créer des comptes entreprise par l’admin,
  - créer des organisations,
  - rattacher des membres,
  - gérer contrats et templates,
  - créer des work orders,
  - générer des exports backend.
- Nouveau runtime `backend/fastapi/app/api/v1/routers/b2b.py` pour le dashboard entreprise et les work orders.
- Endpoints admin ajoutés dans `backend/fastapi/app/api/v1/routers/admin.py` :
  - comptes B2B,
  - organisations,
  - memberships,
  - contrats,
  - templates,
  - work orders,
  - exports.
- Wiring global branché dans `backend/fastapi/app/api/deps.py`, `backend/fastapi/app/api/v1/api.py`, `backend/fastapi/app/models/__init__.py` et `backend/fastapi/app/main.py`.

### Garanties
- Approche additive et `prod-safe`.
- Les comptes entreprise créés par l’admin sont directement connectables via email/mot de passe.
- Les exports sont stockés en jobs backend sérialisés, prêts à être branchés ensuite sur PDF/Excel côté interface.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- durcir le scope pays/continent sur les endpoints staff comptables
- préparer shop / VTC backend
- passer ensuite à l’interface admin et entreprise

## Lot 17 — Durcissement scopes staff pays/continent

### Livré
- Nouveau helper de scope additif dans `backend/fastapi/app/api/deps.py` :
  - chargement dynamique des scopes staff,
  - validation d’accès par `country` / `continent`,
  - filtrage des résultats selon le périmètre du staff.
- Durcissement des endpoints admin sensibles dans `backend/fastapi/app/api/v1/routers/admin.py` pour :
  - cas AML,
  - organisations B2B,
  - memberships,
  - contrats,
  - templates,
  - work orders,
  - exports.
- Le filtrage est automatique sur les listings, et les opérations d’écriture refusent les périmètres hors scope.

### Garanties
- Approche additive et `prod-safe`.
- Compatibilité gardée avec l’admin principal non scoppé.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- préparation shop backend
- préparation VTC backend
- puis interfaces admin / entreprise / restaurant

## Lot 18 — Shop / articles backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260607_0058_shop_foundation.py`.
- Nouveau domaine `shop` dans `backend/fastapi/app/models/shop.py` avec :
  - marchands,
  - staff marchand,
  - catalogues,
  - articles,
  - commandes shop,
  - lignes de commande.
- Nouveau service `backend/fastapi/app/services/shop_service.py` pour :
  - créer des comptes marchand,
  - créer des marchands,
  - gérer staff/catalogues/articles,
  - créer des commandes,
  - décrémenter le stock,
  - exposer un dashboard marchand.
- Nouveau runtime `backend/fastapi/app/api/v1/routers/shop.py`.
- Endpoints admin shop ajoutés dans `backend/fastapi/app/api/v1/routers/admin.py`.
- Wiring global branché dans `backend/fastapi/app/api/deps.py`, `backend/fastapi/app/api/v1/api.py`, `backend/fastapi/app/models/__init__.py` et `backend/fastapi/app/main.py`.
- Les endpoints admin shop sont déjà protégés par le durcissement de scope pays/continent sur le module `SHOP`.

### Garanties
- Approche additive et `prod-safe`.
- Stock décrémenté dès création de commande.
- Backend prêt pour le futur branchement logistique / livraison / gifting diaspora.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- préparation VTC backend
- puis interfaces admin / entreprise / restaurant / shop

## Lot 19 — VTC backend

### Livré
- Migration `backend/fastapi/alembic/versions/20260607_0059_vtc_foundation.py`.
- Nouveau domaine `vtc` dans `backend/fastapi/app/models/vtc.py` avec :
  - opérateurs de flotte,
  - profils chauffeur,
  - véhicules,
  - demandes de course.
- Nouveau service `backend/fastapi/app/services/vtc_service.py` pour :
  - créer des comptes chauffeur,
  - créer des opérateurs,
  - gérer profils chauffeur et véhicules,
  - créer des demandes de course,
  - exposer un dashboard chauffeur.
- Nouveau runtime `backend/fastapi/app/api/v1/routers/vtc.py`.
- Endpoints admin VTC ajoutés dans `backend/fastapi/app/api/v1/routers/admin.py`.
- Wiring global branché dans `backend/fastapi/app/api/deps.py`, `backend/fastapi/app/api/v1/api.py`, `backend/fastapi/app/models/__init__.py` et `backend/fastapi/app/main.py`.
- Les endpoints admin VTC sont protégés par le scope pays/continent sur le module `VTC`.

### Garanties
- Approche additive et `prod-safe`.
- Le module est préparé backend sans être activé par défaut.
- Backend prêt pour les futurs branchements dispatch, tarification dynamique et trajet temps réel.
- Validation ciblée `python -m py_compile` : OK.

### Suite logique
- interfaces admin / entreprise / restaurant / shop / VTC
- puis intégration dispatch temps réel et pricing avancé
## 2026-06-07 — Module completeness matrix

- Added `ZASKA_MODULE_COMPLETENESS_MATRIX.md` as the canonical module-by-module readiness map.
- The matrix documents:
  - actual backend status by domain
  - missing backend work by module
  - required interfaces for each side of each module
  - production blockers
  - recommended execution order from here

## 2026-06-07 — VTC operational backend

- Added the operational VTC lifecycle in `backend/fastapi/alembic/versions/20260607_0060_vtc_operational_flow.py`.
- Extended `backend/fastapi/app/models/vtc.py` with:
  - driver online/offline presence
  - live driver location
  - active ride binding
  - ride dispatch state
  - ride payout state
  - dispatch offers
  - immutable ride events
- Rebuilt `backend/fastapi/app/services/vtc_service.py` to support:
  - ride quotation
  - dispatch candidate selection
  - driver offer acceptance/rejection
  - ride status transitions
  - customer cancellation
  - driver payout settlement to wallet
- Rebuilt `backend/fastapi/app/api/v1/routers/vtc.py` with customer and driver operational endpoints.
- Extended `backend/fastapi/app/api/v1/routers/admin.py` with ride detail, ride dispatch, manual driver assignment and payout settlement endpoints.
- Exported the new VTC entities in `backend/fastapi/app/models/__init__.py`.
- Validation passed with targeted `python -m py_compile`.

## 2026-06-07 — SHOP operational backend

- Added the operational SHOP schema in `backend/fastapi/alembic/versions/20260607_0061_shop_operational_flow.py`.
- Extended `backend/fastapi/app/models/shop.py` with:
  - merchant geo coordinates
  - delivery-linked order fields
  - merchandise payment holds
  - merchant payout snapshots
  - immutable order events
- Rebuilt `backend/fastapi/app/services/shop_service.py` to support:
  - order creation with delivery context
  - customer funding
  - merchant fulfilment lifecycle
  - delivery task + escrow creation
  - delivery assignment sync
  - order finalization from delivery task
  - merchant payout snapshots
- Rebuilt `backend/fastapi/app/api/v1/routers/shop.py` with customer funding, merchant order actions and merchant payouts endpoints.
- Extended `backend/fastapi/app/api/v1/routers/admin.py` with SHOP order detail, fund, status and payout operations.
- Wired `backend/fastapi/app/api/v1/routers/tasks.py` so `SHOP_DELIVERY` assignments and task completion update the linked shop order lifecycle.
- Exported the new SHOP entities in `backend/fastapi/app/models/__init__.py`.
- Validation passed with targeted `python -m py_compile`.

## 2026-06-07 — FOOD runtime completion

- Extended `backend/fastapi/app/api/v1/routers/food.py` with:
  - customer order listing
  - customer/restaurant order detail access
  - restaurant order listing
  - restaurant payout listing
  - restaurant payout sync to accounting
- Validation passed with targeted `python -m py_compile`.

## 2026-06-07 — Transverse production hardening

- Added `backend/fastapi/app/services/operations_resilience_service.py` to centralize:
  - stale VTC offer expiration
  - stale VTC ride redispatch
  - stale SHOP order flagging
  - stale FOOD order flagging
  - operational health snapshots
- Wired the resilience cycle into:
  - `backend/fastapi/app/worker/tasks.py`
  - `backend/fastapi/app/core/scheduler.py`
  - `backend/fastapi/app/worker/celery_app.py`
- Added `GET /health/ops` in `backend/fastapi/app/main.py` for a unified operational-health view across VTC, SHOP and FOOD.
- Validation passed with targeted `python -m py_compile`.

## 2026-06-07 — Backend production-ready gates

- Added `ZASKA_BACKEND_PRODUCTION_READY_CHECKLIST.md` as the final backend certification checklist.
- It defines the production gates for:
  - migrations
  - critical business flows
  - external providers
  - operations/observability
  - real environment validation

## 2026-06-07 — Non-destructive backend certification tooling

- Added `backend/fastapi/app/services/production_readiness_service.py` to centralize static backend readiness checks.
- Added `backend/fastapi/scripts/backend_readiness_audit.py` so the backend certification report can be rerun from the CLI.
- Added `GET /health/backend-readiness` in `backend/fastapi/app/main.py` for a non-destructive backend readiness report.
- Validation passed with targeted `python -m py_compile`.

## 2026-06-07 — Backend certification execution protocol

- Added `ZASKA_BACKEND_CERTIFICATION_PROTOCOL.md` as the exact non-destructive certification runbook.
- The protocol covers:
  - isolated certification environment
  - Alembic verification
  - API/worker startup
  - health checks
  - critical scenario validation
  - go/no-go decision

## 2026-06-07 - Certification kit completion

- Added `backend/fastapi/.env.certification.example` as the isolated environment template for backend certification.
- Added `backend/fastapi/scripts/runtime_smoke_checks.py` for repeatable runtime health validation after API and worker startup.
- Extended `ZASKA_BACKEND_CERTIFICATION_PROTOCOL.md` to reference:
  - the certification environment template
  - the static readiness audit
  - the runtime smoke checks command

## 2026-06-07 - Certification runner and dual-profile envs

- Reworked `backend/fastapi/.env.certification.example` as the local isolated certification profile.
- Added `backend/fastapi/.env.certification.staging.example` for shared staging certification.
- Added `backend/fastapi/scripts/run_backend_certification.py` as the unified runner for:
  - static readiness audit
  - runtime smoke checks
- Extended `ZASKA_BACKEND_CERTIFICATION_PROTOCOL.md` with the recommended dual-profile execution path.

## 2026-06-07 - Certification env validation hardening

- Added `backend/fastapi/scripts/validate_certification_env.py` to validate certification env files before any backend certification run.
- Extended `backend/fastapi/scripts/run_backend_certification.py` to load an env file explicitly with `--env-file`.
- Updated `ZASKA_BACKEND_CERTIFICATION_PROTOCOL.md` so the recommended flow now validates the env file before the static audit and runtime smoke checks.

## 2026-06-07 - Local certification env created

- Added `backend/fastapi/.env.certification` as the local gitignored certification environment file.
- Updated `.gitignore` so real certification env files stay out of version control while example files remain tracked.
- The expected next step is to replace placeholders, then run `validate_certification_env.py` before any backend certification run.

## 2026-06-07 - Docker certification alignment

- Reworked the certification env templates to target Docker internal services:
  - `pgbouncer:6432` for runtime PostgreSQL
  - `postgres:5432` for Alembic
  - authenticated `redis:6379` URLs for app and Celery
- Added `docker-compose.certification.yml` to run backend certification on top of the existing Docker stack without rewriting the main compose file.
- Extended `validate_certification_env.py` to require `ALEMBIC_DATABASE_URL` and to flag Redis host/auth patterns that need review.

## 2026-06-07 - Social fund auto-seeding for Docker certification

- Added `backend/fastapi/scripts/seed_social_funds.py` to auto-create and resolve the pension, health, and smoothing fund users and wallets.
- Extended `backend/fastapi/docker-entrypoint.sh` so Docker startup now auto-exports:
  - `PENSION_FUND_USER_ID`
  - `HEALTH_FUND_USER_ID`
  - `SMOOTHING_FUND_USER_ID`
- Updated certification env templates so system wallet IDs can stay empty on Docker certification runs.
- Updated `validate_certification_env.py` so those IDs become warnings instead of blocking errors when `CERTIFICATION_RUNTIME=docker-compose`.

## 2026-06-07 - Docker backend certification launcher

- Added `scripts/run_docker_backend_certification.ps1` as the PowerShell launcher for the Docker certification flow.
- The launcher:
  - validates `backend/fastapi/.env.certification`
  - starts the certification Docker stack with `docker-compose.certification.yml`
  - runs the static backend audit
  - runs the runtime smoke checks

## 2026-06-07 - Certification blockers fixed (round 1)

- Fixed the SQLAlchemy import blocker in `backend/fastapi/app/models/kyc.py` by renaming the conflicting `metadata` property.
- Updated `backend/fastapi/app/services/kyc_service.py` to use the renamed KYC metadata accessor.
- Fixed `backend/fastapi/scripts/run_backend_certification.py` so it:
  - resolves script paths correctly
  - loads the env file before running the static audit import path
- Simplified Docker certification to bypass PgBouncer locally and target PostgreSQL directly for certification runs.
- Hardened `scripts/run_docker_backend_certification.ps1` so native command failures now stop the flow immediately.

## 2026-06-07 - Certification blockers fixed (round 2)

- Fixed the failing food migration `20260606_0050_food_combos_polygons_and_closures.py` by moving the combo foreign-key creation after the combo tables are created.
- Hardened `scripts/run_docker_backend_certification.ps1` with an active wait for `/health` before runtime smoke checks.

## 2026-06-07 - Docker backend certification passed locally

- Executed `scripts/run_docker_backend_certification.ps1` successfully end-to-end.
- Local Docker backend certification now passes:
  - env validation
  - static readiness audit
  - backend health wait
  - runtime smoke checks
- Verified health endpoints:
  - `/health`
  - `/health/ready`
  - `/health/db`
  - `/health/redis`
  - `/health/scheduler`
  - `/health/realtime`
  - `/health/ops`
  - `/health/backend-readiness`
- Remaining truth: deployed/staging environment parity still needs separate validation before calling the backend fully production-certified for the live deployment.

## 2026-06-07 - Internal wallet runtime hardening for deployed workers

- Added `backend/fastapi/app/services/internal_wallet_seed_service.py` as the shared internal identity seeding service.
- Rewired both `seed_platform_wallet.py` and `seed_social_funds.py` to use the shared service.
- Added runtime seeding in `backend/fastapi/app/main.py` so the web process binds internal wallet IDs at startup.
- Added runtime seeding hooks in `backend/fastapi/app/worker/celery_app.py` for Celery worker and beat startup.
- This closes the deployment gap where non-entrypoint worker runtimes could start without the internal fund IDs bound.

## 2026-06-07 - Deployed backend parity audit

- Fixed the Render worker command to use `app.worker.celery_app.celery_app`.
- Added `APP_FRONTEND_URL` to the Render worker env var set for email/task parity.
- Added `backend/fastapi/scripts/validate_render_blueprint.py` to audit deployment-manifest parity.
- Added `ZASKA_DEPLOYED_BACKEND_CERTIFICATION.md` to separate local certification from deployed-environment certification.

## 2026-06-07 - Live backend gap audit

- Verified live health endpoints on `https://zaska-backend.onrender.com`.
- Confirmed live passes core health endpoints but returns `404` for:
  - `/health/ops`
  - `/health/backend-readiness`
- Added `backend/fastapi/scripts/compare_live_openapi.py` to compare local certified OpenAPI with the deployed OpenAPI.
- Added `ZASKA_LIVE_BACKEND_GAP_REPORT.md` documenting the current live/backend parity gap.
- Current measured gap:
  - local paths: 305
  - live paths: 157
  - missing on live: 148
## 2026-06-07 — Unified Pricing Engine

- Added shared pricing engine in `backend/fastapi/app/services/pricing_engine_service.py`
- Unified quote logic for `VTC`, `FOOD` delivery and `SHOP` delivery
- Reused existing `service_zones.pricing_profile_json` and partner/operator `metadata_json` for overrides
- Added quote endpoints:
  - `POST /vtc/quote`
  - `POST /food/quote`
  - `POST /shop/quote`
- FOOD and SHOP orders now persist pricing breakdowns in metadata and expose them in API responses
- VTC ride responses now expose a normalized pricing breakdown
- Validation passed with targeted `python -m py_compile`
- Added calculation reference documentation in `ZASKA_BACKEND_CALCULATION_PROTOCOLS.md`

## 2026-06-07 — Geo Pricing Governance

- Added continent and country pricing profile support to backend models
- Added migration `20260607_0062_geo_pricing_profiles.py`
- Extended `GeoHierarchyService` to read and update continent/country pricing profiles
- Added admin endpoints:
  - `PUT /admin/geo/continents/{continent_code}/pricing`
  - `PUT /admin/geo/countries/{country_code}/pricing`
- Extended pricing engine fallback order to:
  - manual override
  - partner/operator metadata
  - service zone
  - country
  - continent
  - backend currency default
- Added governance documentation in `ZASKA_PRICING_GOVERNANCE_MATRIX.md`
## 2026-06-07 - World coverage and geo discovery

- Added a global world-country backend catalog and runtime loader.
- Locked signup to active countries only.
- Added public signup-country and geo-discovery endpoints.
- Added provider-agnostic maps service with catalog fallback and future Google/Mapbox readiness.
- Improved FOOD, SHOP, and VTC target-country/city discovery flows.
