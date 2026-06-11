# ZASKA Master Action Plan

Plan d’action opérationnel de référence.

But :
- permettre de suivre le projet même si l’exécution s’interrompt
- garder une feuille de route claire, complète et ordonnée
- éviter tout bricolage
- prioriser le backend et les migrations avant les interfaces

Document lié :
- `ZASKA_EXPANSION_ARCHITECTURE.md`
- `ZASKA_CAHIER_DES_CHARGES_MASTER.md`

Date : `2026-06-06`

---

## 1. Principes de conduite

- production existante = **zéro casse**
- toute évolution DB = **migration additive avec rollback**
- toute fonctionnalité = **désactivable par admin principal**
- tout domaine métier = **modèles + services + permissions + audit**
- backend d’abord, frontend ensuite
- sécurité, maintenabilité, scalabilité et observabilité à chaque étape
- pas de code “temporaire” destiné à rester

---

## 2. Mode d’exécution

Chaque lot suit toujours la même séquence :

1. audit du domaine
2. design technique
3. migration DB
4. modèles SQLAlchemy
5. services métier
6. endpoints / jobs / permissions
7. tests ciblés
8. activation admin
9. documentation mise à jour

Définition de terminé pour un lot :
- migrations présentes
- rollback possible
- services métier testables
- permissions branchées
- activation/désactivation admin prévue
- rien de critique en dur dans le code

---

## 3. Vision macro des chantiers

### Phase 0 — Gouvernance technique
- [ ] figer le backlog de référence
- [ ] figer les conventions backend
- [ ] figer les conventions migrations
- [ ] lister les dettes techniques connues
- [ ] définir les statuts par lot : `todo`, `in_progress`, `blocked`, `done`

### Phase 1 — Fondations d’accès et d’activation
- [ ] RBAC staff/admin scoppé
- [ ] module registry unifié
- [ ] hiérarchie continent/pays/ville/zone
- [ ] moteur de résolution d’activation
- [ ] journal d’audit des changements admin

### Phase 2 — Socle comptable et conformité
- [ ] séparation wallet / ledger
- [ ] comptes financiers par zone / fonds / module
- [ ] moteur fiscal TVA B2B/B2C
- [ ] moteur AML
- [ ] réconciliation et snapshots

### Phase 3 — Domaines métier cœur
- [ ] tâches et matching avancés
- [ ] food backend complet
- [ ] abonnements
- [ ] boutique/articles
- [ ] B2B

### Phase 4 — Opérations et contrôle
- [ ] litiges avancés
- [ ] support ops
- [ ] rôles comptables scoppés
- [ ] exports / reporting
- [ ] notifications avancées

### Phase 5 — Domaines futurs préparés
- [ ] VTC inactif mais prêt
- [ ] autres modules futurs activables

### Phase 6 — Interfaces
- [ ] admin
- [ ] client
- [ ] tasker
- [ ] restaurant
- [ ] entreprise
- [ ] support
- [ ] comptable

---

## 4. Lots détaillés dans l’ordre recommandé

## Lot 0 — Stabilisation documentaire et architecture

### Objectif
Créer le cadre de pilotage stable.

### Livrables
- [ ] document d’architecture
- [ ] cahier des charges consolidé
- [ ] plan d’action exécutable
- [ ] backlog des domaines
- [ ] matrice des dépendances

### Statut
- [x] architecture
- [x] plan d’action
- [x] cahier des charges
- [ ] backlog d’exécution détaillé par tickets

---

## Lot 1 — IAM / RBAC / Scopes

### Objectif
Permettre au système de gérer plusieurs rôles, plusieurs profils et des accès scoppés.

### À créer
- [ ] `roles`
- [ ] `permissions`
- [ ] `role_permissions`
- [ ] `user_profiles`
- [ ] `user_role_assignments`
- [ ] `admin_scopes`
- [ ] `admin_invitations`
- [ ] `staff_password_resets` ou mécanisme équivalent

### Backend
- [ ] service RBAC
- [ ] service invitations staff
- [ ] middleware / dependency de scope
- [ ] création compte staff par admin principal
- [ ] login staff avec identifiants assignés

### Cas couverts
- [ ] admin principal
- [ ] comptable par pays
- [ ] comptable par continent
- [ ] agent support
- [ ] agent KYC
- [ ] modérateur
- [ ] manager opérations
- [ ] restaurant staff plus tard

### Définition de terminé
- [ ] aucun staff n’utilise un simple `users.role` seul
- [ ] scopes pays / continent / modules opérationnels
- [ ] accès refusé hors périmètre

---

## Lot 2 — Module Registry / Activation Admin

### Objectif
Faire exister tous les modules dans le backend, mais activables/désactivables par admin sans code.

### À créer
- [ ] `platform_modules`
- [ ] `continent_module_settings`
- [ ] `country_module_settings`
- [ ] `city_module_settings` si nécessaire
- [ ] `module_activation_audit`

### Modules minimum
- [ ] `TASKS`
- [ ] `FOOD`
- [ ] `SHOP`
- [ ] `SUBSCRIPTIONS`
- [ ] `B2B`
- [ ] `DIASPORA`
- [ ] `TRANSPORT`
- [ ] `SOCIAL_PROTECTION`
- [ ] `ACCOUNTING`
- [ ] `KYC_ADVANCED`

### Backend
- [ ] moteur de résolution `is_module_enabled()`
- [ ] héritage `global -> continent -> pays -> ville`
- [ ] endpoints admin principal
- [ ] logs des bascules

### Définition de terminé
- [ ] l’admin principal peut activer/désactiver un module par périmètre
- [ ] les routes backend respectent cette activation

---

## Lot 3 — Géographie Hiérarchique

### Objectif
Sortir d’un modèle limité au pays pour supporter food, VTC, shop, diaspora et comptabilité zonée.

### À créer / compléter
- [ ] `continents`
- [ ] `countries` enrichi
- [ ] `cities`
- [ ] `service_zones`
- [ ] `zone_pricing_profiles`
- [ ] `zone_availability`

### Décisions
- [ ] séparation continent / pays / ville
- [ ] zone de service configurable
- [ ] rattachement modules et pricing aux zones

### Définition de terminé
- [ ] un module peut être activé pour un continent, un pays ou une ville
- [ ] les adresses et disponibilités peuvent s’appuyer dessus

---

## Lot 4 — Ledger Comptable et Comptes Financiers

### Objectif
Avoir une vraie base comptable robuste et auditable.

### À créer
- [ ] `financial_accounts`
- [ ] `financial_account_scopes`
- [ ] `ledger_entries`
- [ ] `fund_transfers`
- [ ] `reconciliation_snapshots`
- [ ] `country_revenue_snapshots`

### Backend
- [ ] service ledger
- [ ] séparation wallet utilisateur / ledger comptable
- [ ] snapshots quotidiens
- [ ] drift detection
- [ ] reporting par fonds / zone / module

### Définition de terminé
- [ ] tous les flux critiques peuvent être réconciliés
- [ ] les comptables voient uniquement leur périmètre

---

## Lot 5 — Fiscalité TVA B2B / B2C

### Objectif
Supporter proprement la TVA, les exemptions et les exports fiscaux.

### À créer
- [ ] `tax_profiles`
- [ ] `vat_registrations`
- [ ] `tax_rules`
- [ ] `tax_ledger`
- [ ] `tax_reports`

### Backend
- [ ] moteur de calcul TVA
- [ ] distinction `particulier` / `entreprise`
- [ ] support numéro TVA / équivalent
- [ ] export par pays

### Définition de terminé
- [ ] la TVA est traçable et exportable
- [ ] le cas B2B est couvert

---

## Lot 6 — AML / Conformité

### Objectif
Sécuriser l’internationalisation et les flux de paiement.

### À créer
- [ ] `aml_flags`
- [ ] `aml_cases`
- [ ] `aml_threshold_events`
- [ ] `aml_reports`
- [ ] `sanctions_screenings`

### Backend
- [ ] seuil transaction
- [ ] seuil mensuel
- [ ] patterns suspects
- [ ] blocage et revue admin
- [ ] reporting autorité

### Définition de terminé
- [ ] les règles AML sont automatiques et auditables

---

## Lot 7 — Food Backend Core

### Objectif
Créer le vrai domaine food backend complet.

### À créer
- [ ] `restaurants`
- [ ] `restaurant_staff`
- [ ] `restaurant_locations`
- [ ] `restaurant_hours`
- [ ] `restaurant_kyc_documents`
- [ ] `restaurant_menu_items`
- [ ] `restaurant_menu_item_options`
- [ ] `restaurant_menu_item_images`
- [ ] `restaurant_promotions`
- [ ] `food_orders`
- [ ] `food_order_items`
- [ ] `food_order_status_history`
- [ ] `food_delivery_assignments`
- [ ] `delivery_pricing`

### Backend
- [ ] onboarding restaurant
- [ ] catalogue menu
- [ ] panier
- [ ] checkout
- [ ] restaurant confirme la préparation
- [ ] dispatch livreur
- [ ] OTP livraison
- [ ] split repas / livraison
- [ ] commission restaurant

### Dépendances
- [ ] lot 1
- [ ] lot 2
- [ ] lot 3
- [ ] lot 4
- [ ] lot 5

---

## Lot 8 — Carnet d’Adresses Universel et Bénéficiaires

### Objectif
Unifier tâches, food, shop et commandes à distance.

### À compléter
- [ ] `beneficiaries`
- [ ] `delivery_contacts`
- [ ] `service_locations`
- [ ] liens avec `user_addresses`

### Cas à couvrir
- [ ] pour moi
- [ ] pour un tiers
- [ ] adresse d’exécution
- [ ] adresse de collecte
- [ ] adresse de livraison
- [ ] pays différent
- [ ] OTP bénéficiaire

---

## Lot 9 — Abonnements

### Objectif
Construire le moteur complet d’abonnements.

### À créer
- [ ] `subscription_plans`
- [ ] `subscriptions`
- [ ] `service_subscriptions`
- [ ] `subscription_service_schedules`
- [ ] `subscription_wallets`
- [ ] `subscription_charges`
- [ ] `subscription_assignments`
- [ ] `subscription_contracts`

### Backend
- [ ] Zaska Pro
- [ ] abonnements par service
- [ ] récurrence
- [ ] prélèvements
- [ ] pause / reprise / suspension
- [ ] compte virtuel d’abonnement

---

## Lot 10 — Boutique / Articles

### Objectif
Permettre les ventes d’articles à distance avec livraison locale.

### À créer
- [ ] `merchants`
- [ ] `merchant_staff`
- [ ] `merchant_catalog_items`
- [ ] `merchant_item_categories`
- [ ] `merchant_orders`
- [ ] `merchant_order_items`
- [ ] `merchant_delivery_assignments`

### Backend
- [ ] onboarding marchand
- [ ] catalogue
- [ ] stock / disponibilité
- [ ] gifting à distance
- [ ] split livraison
- [ ] commission vendeur

---

## Lot 11 — B2B

### Objectif
Créer le domaine entreprise séparé du flux grand public.

### À créer
- [ ] `companies`
- [ ] `company_users`
- [ ] `company_billing_profiles`
- [ ] `company_service_contracts`
- [ ] `company_subscription_plans`

### Backend
- [ ] onboarding entreprise
- [ ] facturation
- [ ] utilisateurs entreprise
- [ ] périmètre contrats
- [ ] tâches récurrentes entreprise

---

## Lot 12 — Notation Bidirectionnelle

### Objectif
Mettre la notation multidimensionnelle complète.

### À créer
- [ ] `task_reviews`
- [ ] `client_reviews`
- [ ] `rating_dimensions`
- [ ] `rating_aggregates`

### Backend
- [ ] notation client -> tasker
- [ ] notation tasker -> client
- [ ] agrégations
- [ ] suspensions auto
- [ ] restrictions premium auto

---

## Lot 13 — Parrainage

### Objectif
Construire le système de parrainage tasker et client.

### À créer
- [ ] `referral_codes`
- [ ] `referral_links`
- [ ] `referral_rewards`
- [ ] `referral_campaigns`

---

## Lot 14 — Litiges Avancés

### Objectif
Passer au vrai centre `FROZEN_AUDIT`.

### À créer
- [ ] `dispute_cases`
- [ ] `dispute_evidence`
- [ ] `dispute_status_history`
- [ ] `dispute_assignments`
- [ ] `frozen_audit_records`

---

## Lot 15 — VTC Préparé mais Inactif

### Objectif
Préparer l’architecture sans ouvrir le service.

### À créer
- [ ] `drivers`
- [ ] `driver_documents`
- [ ] `vehicles`
- [ ] `transport_rides`
- [ ] `transport_pricing_profiles`
- [ ] `transport_dispatch_events`

### Contraintes
- [ ] module désactivé par défaut
- [ ] activation admin par zone
- [ ] KYC conducteur renforcé

---

## Lot 16 — Interfaces

À démarrer seulement après stabilisation backend suffisante.

### Interfaces à construire / refondre
- [ ] client
- [ ] tasker
- [ ] restaurant
- [ ] entreprise
- [ ] admin principal
- [ ] support
- [ ] comptable scoped

---

## 5. Exigences UX à ne jamais oublier

### Principes
- [ ] maximum 3 clics pour l’action principale
- [ ] pas de surprise tarifaire
- [ ] états clairs
- [ ] flows cohérents entre tâches, food, shop
- [ ] activation invisible si module désactivé
- [ ] message clair si pays/zone non couverte
- [ ] adresses réutilisables partout
- [ ] commandes pour soi ou pour un tiers simples

### UX critique par produit
- [ ] tasker : paiement, protection sociale, badges, sécurité visibles
- [ ] client : prix final clair, taxes claires, adresses faciles
- [ ] restaurant : dashboard distinct, pas interface client maquillée
- [ ] comptable : uniquement ses chiffres, pas de bruit
- [ ] admin principal : pilotage simple, sans passer par le code

---

## 6. Risques à surveiller

- [ ] surcharger `users.role`
- [ ] surcharger `tasks` pour faire `food` ou `vtc`
- [ ] laisser la logique d’activation dispersée
- [ ] avoir plusieurs sources de vérité comptable
- [ ] exposer les données globales aux mauvais profils
- [ ] avancer trop vite sur le frontend sans socle backend

---

## 7. Rythme conseillé

### À faire en continu
- [ ] mettre à jour ce document après chaque lot
- [ ] marquer ce qui est `fait / partiel / manquant`
- [ ] documenter les décisions d’architecture
- [ ] noter les changements de priorité

### Format de mise à jour
- date
- lot
- objectif
- fichiers touchés
- migration ajoutée
- risques
- reste à faire

---

## 8. Priorité immédiate

Les **3 prochains chantiers obligatoires** sont :

1. **Lot 1 — IAM / RBAC / Scopes**
2. **Lot 2 — Module Registry / Activation Admin**
3. **Lot 3 — Géographie Hiérarchique**

Tant que ces 3 socles ne sont pas propres, la suite restera fragile.


---

## 9. Backend Progress Log

### 2026-06-06 - Lot 1 foundation (completed, phase 1 partial)

- Scope: backend + database foundation only
- Migration added: `backend/fastapi/alembic/versions/20260606_0042_access_control_foundation.py`
- Models added:
  - `access_roles`
  - `access_permissions`
  - `access_role_permissions`
  - `access_user_role_assignments`
  - `access_admin_scopes`
- Service added: `backend/fastapi/app/services/access_control_service.py`
- Dependencies added:
  - platform admin compatibility guard
  - permission dependency factory
- Admin endpoints added:
  - `GET /api/admin/access-control/catalog`
  - `GET /api/admin/staff`
  - `POST /api/admin/staff`
  - `PUT /api/admin/staff/{user_id}/roles`
  - `PUT /api/admin/staff/{user_id}/scopes`
- Compatibility kept:
  - legacy `users.role == admin` still works as principal admin
  - new RBAC layer is additive, not destructive
- Validation done:
  - targeted `py_compile` passed on new backend files

### Remaining inside Lot 1

- staff invitations
- staff password reset / rotation flow
- immutable RBAC audit trail
- scope enforcement across all admin routes
- module-aware scope resolution

### 2026-06-06 - Lot 2 foundation (completed, phase 1 continuing)

- Scope: backend + database module registry foundation only
- Migration added: `backend/fastapi/alembic/versions/20260606_0043_module_registry_foundation.py`
- Models added:
  - `platform_modules`
  - `module_activation_settings`
  - `module_activation_audit`
- Service added: `backend/fastapi/app/services/module_control_service.py`
- Runtime integration added:
  - `/api/system/bootstrap` now exposes unified `modules`
  - `/api/users/me` now exposes `runtimeModules`
  - `/api/tasks/*` now respects the `TASKS` module gate
- Admin endpoints added:
  - `GET /api/admin/modules/catalog`
  - `GET /api/admin/modules/settings`
  - `GET /api/admin/modules/runtime/{country_code}`
  - `PUT /api/admin/modules/{module_code}/settings`
- Compatibility kept:
  - legacy country food toggle is synchronized with module `FOOD`
  - legacy feature flag `food_delivery_enabled` stays aligned
- Validation done:
  - targeted `py_compile` passed on new backend files

### Remaining inside Lot 2

- scope-aware enforcement on more non-task modules
- richer continent/city resolution from the future geo hierarchy
- unified admin UI wiring for module controls

### 2026-06-06 - Lot 3 foundation (completed, phase 1 continuing)

- Scope: backend + database geography hierarchy foundation only
- Migration added: `backend/fastapi/alembic/versions/20260606_0044_geography_hierarchy_foundation.py`
- Models added:
  - `continents`
  - `cities`
  - `service_zones`
- Country compatibility fields added:
  - `countries.continent_code`
  - `countries.continent_name`
  - `countries.primary_city_name`
- Service added: `backend/fastapi/app/services/geo_hierarchy_service.py`
- Runtime integration added:
  - `/api/system/bootstrap` now exposes `geo`
  - `/api/users/me` now exposes `geoHierarchy`
  - module control now derives continent scope from geography service
- Admin endpoints added:
  - `GET /api/admin/geo/continents`
  - `GET /api/admin/geo/countries`
  - `GET /api/admin/geo/countries/{country_code}`
  - `GET /api/admin/geo/cities`
  - `PUT /api/admin/geo/cities`
  - `GET /api/admin/geo/service-zones`
  - `PUT /api/admin/geo/service-zones`
- Compatibility kept:
  - legacy `countries.city` remains intact and is synchronized with primary city
  - country rollout continues to work without frontend changes
- Validation done:
  - targeted `py_compile` passed on new backend files

### Remaining inside Lot 3

- world-scale country and city bulk seeding strategy
- address normalization linked to city and zone ids
- geo-aware task and food matching runtime
- continent and city activation UI on admin side

### 2026-06-06 - Lot 4 foundation (completed, phase 1 continuing)

- Scope: backend + database accounting ledger foundation only
- Migration added: `backend/fastapi/alembic/versions/20260606_0045_accounting_ledger_foundation.py`
- Models added:
  - `financial_accounts`
  - `financial_account_scopes`
  - `ledger_entries`
  - `fund_transfers`
  - `reconciliation_snapshots`
  - `country_revenue_snapshots`
- Service added: `backend/fastapi/app/services/accounting_ledger_service.py`
- Startup seed added:
  - chart of accounts is now seeded at application boot
- Admin endpoints added:
  - `GET /api/admin/ledger/overview`
  - `GET /api/admin/ledger/accounts`
  - `POST /api/admin/ledger/ingest-wallet-mirror`
  - `POST /api/admin/ledger/reconciliation-snapshots`
  - `GET /api/admin/ledger/reconciliation-snapshots`
  - `POST /api/admin/ledger/country-revenue-snapshots`
  - `GET /api/admin/ledger/country-revenue-snapshots`
- Runtime behavior now supported:
  - system fund wallets can be mirrored into a dedicated accounting ledger
  - tasker net distributions can be mirrored into a synthetic distribution account
  - reconciliation snapshots can compare operational wallet balances vs accounting ledger balances
  - monthly country revenue snapshots can consolidate split totals by country and currency
- Compatibility kept:
  - no existing wallet or transaction flow was replaced
  - the new ledger is additive and can be ingested progressively in production
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 4

- scheduler wiring for automatic ledger ingestion and snapshot generation
- accountant scope filtering by continent and country on ledger endpoints
- export-grade accounting reports and downloadable files
- VAT, withdrawal-fee and FX-margin postings into dedicated accounts

### 2026-06-06 - Lot 5 foundation (completed, phase 1 continuing)

- Scope: backend + database food domain foundation only
- Migration added: `backend/fastapi/alembic/versions/20260606_0046_food_domain_foundation.py`
- Models added:
  - `restaurant_partners`
  - `restaurant_staff_assignments`
  - `restaurant_menus`
  - `restaurant_menu_items`
  - `food_orders`
  - `food_order_items`
- Service added: `backend/fastapi/app/services/food_service.py`
- Runtime router added: `backend/fastapi/app/api/v1/routers/food.py`
- Runtime endpoints added:
  - `GET /api/food/restaurants`
  - `GET /api/food/restaurants/{restaurant_id}`
  - `POST /api/food/orders`
  - `GET /api/food/orders/mine`
  - `GET /api/food/orders/restaurant`
  - `GET /api/food/orders/{order_id}`
  - `POST /api/food/orders/{order_id}/restaurant-status`
- Admin endpoints added:
  - `POST /api/admin/food/restaurant-users`
  - `GET /api/admin/food/restaurants`
  - `POST /api/admin/food/restaurants`
  - `POST /api/admin/food/restaurants/{restaurant_id}/staff`
  - `GET /api/admin/food/restaurants/{restaurant_id}/menus`
  - `POST /api/admin/food/restaurants/{restaurant_id}/menus`
  - `POST /api/admin/food/menus/{menu_id}/items`
  - `GET /api/admin/food/orders`
- Permission catalog extended:
  - `admin.food.read`
  - `admin.food.manage`
- Runtime behavior now supported:
  - food remains module-gated by country through the existing module registry
  - restaurants, menus and menu items are first-class backend entities
  - restaurant users can be provisioned by admin
  - restaurant order flow is now structurally separated from generic task flow
  - meal amount and delivery amount are stored separately for future split logic
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 5

- payment + escrow integration for food orders
- automatic delivery-task creation and dispatch from accepted food orders
- restaurant availability windows and stock management
- service-zone enforcement for restaurant coverage

### 2026-06-06 - Lot 6 foundation (completed, phase 1 continuing)

- Scope: backend + database food payment, delivery-task creation and dispatch foundation
- Migration added: `backend/fastapi/alembic/versions/20260606_0047_food_payment_and_dispatch.py`
- Database extensions added:
  - `food_payment_holds`
  - `food_orders.meal_hold_id`
  - `food_orders.delivery_escrow_id`
  - `food_orders.dispatch_status`
- Runtime behavior now supported:
  - a client can fund a food order
  - meal amount is held separately for later restaurant payout
  - delivery fee creates an actual `FOOD_DELIVERY` task automatically
  - delivery fee also creates a dedicated escrow linked to that task
  - when a tasker accepts the linked delivery task, the food order dispatch state is updated
  - when the delivery task is confirmed complete, the restaurant meal hold is released automatically
  - restaurant cancellation now refunds meal hold and delivery escrow
- Runtime endpoint added:
  - `POST /api/food/orders/{order_id}/fund`
- Existing task runtime integrated:
  - task accept now syncs food dispatch assignment for `FOOD_DELIVERY`
  - task confirm now finalizes the related food order payout lifecycle
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 6

- OTP/double-validation flow specific to diaspora food beneficiaries
- restaurant-side stock depletion and out-of-stock handling
- auto-dispatch prioritization by service zone and distance
- restaurant payout reporting and accounting integration

### 2026-06-06 - Lot 7 foundation (completed, phase 1 continuing)

- Scope: backend + database food operations, service-zone linkage, stock controls and restaurant payout reporting
- Migration added: `backend/fastapi/alembic/versions/20260606_0048_food_ops_and_reporting.py`
- Database extensions added:
  - `restaurant_partners.service_zone_id`
  - `restaurant_partners.accepting_orders`
  - `restaurant_partners.is_temporarily_closed`
  - `restaurant_partners.prep_buffer_minutes`
  - `restaurant_partners.opening_hours_json`
  - `restaurant_menu_items.is_sold_out`
  - `restaurant_menu_items.track_inventory`
  - `restaurant_menu_items.stock_quantity`
  - `restaurant_menu_items.available_from_hour`
  - `restaurant_menu_items.available_to_hour`
  - `restaurant_payout_snapshots`
- Runtime behavior now supported:
  - restaurants can be paused operationally without disabling the whole module
  - menu items can track stock and become sold out automatically
  - dispatch candidates for food delivery can be ranked by distance and readiness
  - payout snapshots per restaurant and period can be generated and listed
  - cancelled food orders restore tracked inventory
- Admin endpoints added:
  - `PATCH /api/admin/food/restaurants/{restaurant_id}/operations`
  - `PATCH /api/admin/food/menu-items/{item_id}/operations`
  - `POST /api/admin/food/dispatch-candidates`
  - `POST /api/admin/food/payout-snapshots`
  - `GET /api/admin/food/payout-snapshots`
- Runtime endpoint added:
  - `POST /api/food/dispatch/candidates`
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 7

- restaurant payout snapshots into accounting ledger
- real service-zone geometry enforcement in food matching
- opening-hours validation against server timezones
- restaurant item modifiers and combo logic

### 2026-06-06 - Lot 8 foundation (completed, phase 1 continuing)

- Scope: backend + database food catalog constraints, timezone-aware availability and accounting sync for restaurant payouts
- Migration added: `backend/fastapi/alembic/versions/20260606_0049_food_catalog_constraints_and_ledger_sync.py`
- Database extensions added:
  - `food_order_items.modifier_total`
  - `restaurant_menu_item_modifier_groups`
  - `restaurant_menu_item_modifier_options`
  - `food_order_item_modifier_selections`
- Runtime behavior now supported:
  - menu items can expose modifier groups and paid options
  - food orders can price modifiers into the order total
  - restaurant opening hours are enforced against local timezone data when available
  - menu item time windows are enforced
  - restaurant service-zone radius can block out-of-zone delivery addresses
  - restaurant payout snapshots can now be synchronized into the accounting ledger
- Admin endpoints added:
  - `GET /api/admin/food/menu-items/{item_id}/modifiers`
  - `POST /api/admin/food/menu-items/{item_id}/modifier-groups`
  - `POST /api/admin/food/modifier-groups/{group_id}/options`
  - `POST /api/admin/food/payout-snapshots/sync-ledger`
- Runtime improvements added:
  - restaurant detail payload now exposes modifiers by item
  - order item payload now exposes modifier totals
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 8

- combo meals and bundled pricing
- richer service-zone polygon geometry beyond radius checks
- timezone-specific restaurant holiday calendars
- customer-side modifier editing and order amendments after creation

### 2026-06-06 - Lot 9 foundation (completed, phase 1 continuing)

- Scope: backend + database combos, special closures, polygon-aware service checks and ledger sync for restaurant payouts
- Migration added: `backend/fastapi/alembic/versions/20260606_0050_food_combos_polygons_and_closures.py`
- Database extensions added:
  - `food_order_items.combo_offer_id`
  - `food_order_items.line_type`
  - `restaurant_special_closures`
  - `restaurant_combo_offers`
  - `restaurant_combo_items`
- Runtime behavior now supported:
  - food orders can contain combo lines
  - combo components can decrement and restore inventory
  - restaurant special closures can block ordering independently of weekly hours
  - first polygon-style service-zone checks are supported when coverage data is present
  - restaurant payout snapshots can be synced toward the accounting ledger
- Admin endpoints added:
  - `GET /api/admin/food/restaurants/{restaurant_id}/closures`
  - `POST /api/admin/food/restaurants/{restaurant_id}/closures`
  - `GET /api/admin/food/restaurants/{restaurant_id}/combos`
  - `POST /api/admin/food/restaurants/{restaurant_id}/combos`
  - `POST /api/admin/food/combos/{combo_id}/items`
- Runtime improvements added:
  - restaurant detail payload now exposes combo offers
  - food ordering accepts combo lines in addition to menu items
- Validation done:
  - targeted `py_compile` passed on new backend files and migration

### Remaining inside Lot 9

- richer polygon and multi-shape geographic validation
- recurring holiday calendars and exception templates
- customer-side order amendment flows after funding
- meal upsell/recommendation logic and advanced bundle rules

### 2026-06-06 - Lot 10 foundation: notation bidirectionnelle et garde-fous automatiques

- Ajout d'une vraie fondation de reviews bidirectionnelles avec migration `backend/fastapi/alembic/versions/20260606_0051_bidirectional_reviews.py`.
- Extension des mod�les `users`, `tasks` et `trust` pour supporter:
  - note client -> tasker multi-crit�res,
  - note tasker -> client multi-crit�res,
  - restriction premium client,
  - statut `tasker_rated` c�t� t�che.
- Nouveau service m�tier `backend/fastapi/app/services/rating_service.py` avec:
  - calcul automatique de la note globale,
  - agr�gats publics,
  - suspension auto tasker si moyenne < 3.5/5 apr�s 10 t�ches,
  - restriction auto client si moyenne < 3/5 apr�s 5 t�ches,
  - notifications automatiques utilisateur/admin,
  - rafra�chissement du trust score apr�s review.
- Compatibilit� legacy conserv�e:
  - `POST /tasks/{task_id}/rate` reste actif,
  - il alimente d�sormais la nouvelle logique multidimensionnelle.
- Nouveaux endpoints backend:
  - `POST /tasks/{task_id}/review/tasker`
  - `POST /tasks/{task_id}/review/client`
  - `GET /trust/reviews/me`
  - `GET /trust/reviews/{user_id}`
- Enrichissement du profil public et priv� avec:
  - ratings `asTasker` / `asClient`,
  - reviews r�centes,
  - restriction premium c�t� client.
- Validation cibl�e r�ussie via `python -m py_compile`.

### 2026-06-06 - Lot 11 foundation: subscriptions backend

- Ajout du domaine backend `subscriptions` avec migration `backend/fastapi/alembic/versions/20260606_0052_subscriptions_foundation.py`.
- Nouveau sch�ma persistant:
  - `subscription_plans`
  - `user_subscriptions`
  - `subscription_usages`
- Nouveau service m�tier `backend/fastapi/app/services/subscription_service.py` avec:
  - seed des plans par d�faut (`Zaska Pro`, m�nage, courses, assistance senior),
  - souscription self-service ou admin,
  - pause / reprise / annulation,
  - aper�u d��ligibilit� par cat�gorie de service,
  - consommation automatique de quota sur cr�ation de t�che,
  - suivi des usages et du quota restant.
- Nouveau router runtime `backend/fastapi/app/api/v1/routers/subscriptions.py`.
- Int�gration admin dans `backend/fastapi/app/api/v1/routers/admin.py` avec lecture / cr�ation / mise � jour des plans et attribution d�abonnement.
- Int�gration du backend tasks:
  - la cr�ation de t�che passe maintenant dans la m�me transaction que l�application �ventuelle d�un abonnement.
- Ajout des permissions admin:
  - `admin.subscriptions.read`
  - `admin.subscriptions.manage`
- Seed du catalogue au d�marrage via `backend/fastapi/app/main.py`.
- Validation cibl�e r�ussie via `python -m py_compile`.

### 2026-06-06 - Lot 12 foundation: referral backend

- Ajout du domaine backend `referral` avec migration `backend/fastapi/alembic/versions/20260606_0053_referral_foundation.py`.
- Nouveau sch�ma persistant:
  - `referral_programs`
  - `referral_events`
  - `referral_rewards`
  - + extension `users.referral_code` / `users.referred_by_user_id`
- Nouveau service m�tier `backend/fastapi/app/services/referral_service.py` avec:
  - seed des programmes par pays + fallback global,
  - g�n�ration de codes de parrainage uniques,
  - rattachement du parrainage � l�inscription,
  - qualification client � la premi�re commande,
  - qualification tasker au 10e job compl�t�,
  - r�compense wallet ou cr�dit plateforme selon le programme.
- Int�gration auth:
  - `RegisterPayload` accepte maintenant `referralCode`,
  - inscription et v�rification OTP exposent le code de parrainage utilisateur.
- Nouveau router runtime/admin `backend/fastapi/app/api/v1/routers/referrals.py`.
- Hooks backend ajout�s au cycle de vie des t�ches:
  - premi�re cr�ation de t�che client,
  - progression tasker � la confirmation de t�che.
- Ajout des permissions admin:
  - `admin.referrals.read`
  - `admin.referrals.manage`
- Seed du catalogue au d�marrage via `backend/fastapi/app/main.py`.
- Validation cibl�e r�ussie via `python -m py_compile`.
