# ZASKA Expansion Architecture

Document de cadrage vivant pour l’évolution de ZASKA.

Documents liés :
- `ZASKA_MASTER_ACTION_PLAN.md`
- `ZASKA_CAHIER_DES_CHARGES_MASTER.md`

Objectif :
- centraliser ce qui existe réellement dans le code
- lister ce qui manque encore
- fixer la stratégie backend + migrations avant d’attaquer les interfaces
- éviter tout bricolage sur une production existante

Date d’audit : `2026-06-06`

---

## 1. Règles d’architecture retenues

### 1.1 Direction générale
- ZASKA reste **une seule plateforme** avec **un seul backend** et **une seule base**.
- Les expériences `client`, `tasker`, `restaurant`, `entreprise`, `admin`, `support`, `comptable`, puis plus tard `transport/VTC` doivent être gérées par **interfaces distinctes** et **permissions distinctes**, pas par des applications totalement indépendantes.
- Vu l’état réel du code actuel, la bonne stratégie n’est **pas** un passage immédiat à 12 microservices.
- La bonne stratégie est un **modular monolith renforcé** :
  - domaines bien séparés
  - migrations additives
  - services métier clairs
  - auditabilité
  - jobs asynchrones
  - activation par configuration admin

### 1.2 Règles absolues
- aucune modification directe de la base en production
- toute évolution DB via migration Alembic avec rollback
- toute nouvelle fonctionnalité activable/désactivable par admin
- toute donnée sensible journalisée
- aucun calcul financier en `float`
- toutes les opérations critiques idempotentes
- séparation stricte :
  - routes
  - services
  - modèles
  - jobs
  - intégrations externes

### 1.3 Ce qu’on doit viser
- sécurité
- maintenabilité
- scalabilité
- auditabilité
- activation progressive par pays / continent / module

---

## 2. Audit réel du backend actuel

## 2.1 Ce qui existe déjà réellement

### Fondations production utiles
- backend FastAPI unique
- migrations Alembic
- wallet / transactions / escrow
- split social Tasker déjà branché
- notifications in-app
- KYC de base + expiration + rappels
- country rollout de base
- social protection events
- trust score / badges
- adresses enregistrées utilisateur
- feature flags par pays
- admin analytics / social / pays
- scheduler + Celery
- audit financier partiel

### Éléments déjà en place ou partiellement en place
- `countries` existe
- `feature_flags` existe
- `user_addresses` existe
- `food_delivery_enabled` existe dans `countries`
- `food_delivery_escrow_minutes` existe
- dashboard social tasker existe
- comptabilité sociale partielle existe
- badges tasker publics commencent à exister
- notifications et centre KYC existent

### Lots déjà construits dans le repo
- rollout pays + sécurité tasker
- split historique + capital social tasker
- moteur de lissage + alertes sociales
- notifications + cycle KYC
- comptabilité admin sociale + premiers badges métier

---

## 2.2 Ce qui est seulement partiel

### Pays / activation
Le système de pays existe, mais il n’est pas encore suffisant pour les ambitions finales.

Limites actuelles :
- activation surtout au niveau **pays**
- pas de vrai niveau **continent / zone opératoire**
- pas de catalogue complet de **modules activables**
- pas de gouvernance hiérarchique `global -> continent -> pays -> ville`
- champ `city` directement dans `countries` : design à revoir

### Rôles utilisateurs
Le système actuel repose surtout sur `users.role` en champ simple.

Problème :
- insuffisant pour :
  - multi-profils utilisateur
  - restaurant
  - entreprise
  - support
  - comptable scoped
  - agent KYC
  - modérateur
  - manager opérations
  - conducteur VTC demain

### Admin / permissions
Il y a un accès admin, mais pas encore un **RBAC structuré et scoppé**.

Il manque :
- rôles admin formels
- scopes pays / continent / module
- administration déléguée
- création staff par admin principal
- login staff avec mot de passe attribué
- cloisonnement comptable strict par périmètre

### Food
Le code prépare un drapeau `food_delivery_enabled`, mais le **vrai domaine food** n’existe pas encore au niveau backend.

Il manque :
- restaurant
- menu
- catalogue plats
- commande food
- panier
- préparation restaurant
- dispatch livreur
- split repas vs livraison
- commission restaurant
- disponibilité articles
- promo restaurant

### Abonnements
Il y a des idées et quelques points isolés, mais pas encore le vrai domaine backend complet.

Il manque :
- abonnement Zaska Pro normalisé
- abonnement par service
- abonnement récurrent B2B/B2C
- calendrier d’exécution
- prélèvements automatiques
- compte virtuel d’abonnement
- logique de pause / reprise / défaut de paiement

### Diaspora / délégation
Le principe existe, mais il faut encore le vrai modèle unifié.

Il manque :
- bénéficiaire tiers normalisé
- adresses pickup / execution / dropoff unifiées
- OTP multi-partie
- visibilité complète du flux transfrontalier

### Litiges
Le support existe, mais pas encore un vrai centre `FROZEN_AUDIT` complet comme demandé.

### TVA / fiscalité
Le pays porte un `tax_rate`, mais pas encore la fiscalité métier complète :
- B2B / B2C
- exemptions
- VAT number validation
- journal fiscal par pays

### AML
Pas encore un domaine AML complet avec seuils, flags, revue et reporting.

### Boutique / articles / VTC
Pas encore modélisés comme domaines backend réels.

---

## 2.3 Ce qui manque complètement au niveau base de données

### Domaine IAM / staff / scopes
À créer :
- `user_profiles`
- `roles`
- `permissions`
- `user_role_assignments`
- `admin_scopes`
- `admin_invitations`
- `staff_accounts` ou équivalent selon choix final

### Domaine modules / activation
À créer :
- `platform_modules`
- `country_module_settings`
- `continent_module_settings`
- éventuellement `city_module_settings`

Modules à gouverner :
- tasks
- food
- shop/articles
- subscriptions
- b2b
- diaspora
- transport
- support
- accounting
- social_protection
- kyc_advanced

### Domaine food
À créer :
- `restaurants`
- `restaurant_staff`
- `restaurant_kyc_documents`
- `restaurant_locations`
- `restaurant_hours`
- `restaurant_categories`
- `restaurant_menu_items`
- `restaurant_menu_item_images`
- `restaurant_menu_item_options`
- `restaurant_promotions`
- `food_orders`
- `food_order_items`
- `food_order_status_history`
- `food_delivery_assignments`
- `delivery_pricing`

### Domaine boutique / articles
À créer :
- `merchants`
- `merchant_staff`
- `merchant_catalog_items`
- `merchant_item_categories`
- `merchant_orders`
- `merchant_order_items`
- `merchant_delivery_assignments`

### Domaine abonnements
À créer :
- `subscriptions`
- `subscription_plans`
- `service_subscriptions`
- `subscription_service_schedules`
- `subscription_wallets`
- `subscription_charges`
- `subscription_assignments`
- `subscription_contracts`

### Domaine B2B
À créer :
- `companies`
- `company_users`
- `company_billing_profiles`
- `company_service_contracts`
- `company_subscription_plans`

### Domaine fiscalité
À créer :
- `tax_profiles`
- `vat_registrations`
- `tax_rules`
- `tax_ledger`
- `tax_reports`

### Domaine AML / conformité
À créer :
- `aml_cases`
- `aml_flags`
- `aml_threshold_events`
- `aml_reports`
- `sanctions_screenings`

### Domaine litiges avancés
À compléter ou refondre :
- `dispute_cases`
- `dispute_evidence`
- `dispute_status_history`
- `dispute_assignments`
- `frozen_audit_records`

### Domaine adresses universelles / bénéficiaires
À compléter :
- `beneficiaries`
- `delivery_contacts`
- `address_book_links`
- `service_locations`

### Domaine comptable avancé
À créer :
- `financial_accounts`
- `financial_account_scopes`
- `ledger_entries`
- `fund_transfers`
- `reconciliation_snapshots`
- `payout_batches`
- `country_revenue_snapshots`

---

## 3. Écarts critiques entre la vision et le code actuel

## 3.1 Le système de rôle est trop faible
Le champ `users.role` ne suffit pas.

Décision :
- garder `users.role` pour compatibilité immédiate
- introduire un système additif de rôles et profils
- migrer progressivement le contrôle d’accès dessus

## 3.2 Le pilotage des modules est trop limité
Aujourd’hui :
- drapeaux pays
- feature flags pays

Demain il faut :
- activation par module
- activation par zone
- activation par type d’acteur
- activation par backend sans redéploiement

## 3.3 Le domaine food n’existe pas encore comme vrai domaine métier
Il faut le concevoir comme un domaine complet, pas comme une variante de task.

Décision :
- réutiliser certains mécanismes task/wallet/escrow
- mais créer des tables food dédiées

## 3.4 Le domaine abonnement n’existe pas encore comme moteur
Il faut un vrai moteur :
- plan
- calendrier
- portefeuille dédié
- prélèvement
- affectation
- support ops

## 3.5 Le RBAC staff scoppé est indispensable
Cas demandé :
- admin principal crée un comptable
- lui affecte pays / continent / modules
- le comptable ne voit que ses chiffres

Le backend actuel ne le permet pas encore proprement.

## 3.6 Il faut isoler les données par périmètre
Le besoin exprimé implique :
- isolation par utilisateur
- isolation par restaurant
- isolation par entreprise
- isolation par pays / continent pour certains rôles

Décision :
- démarrer avec **tenant guard applicatif**
- préparer **RLS PostgreSQL** sur les tables sensibles
- ne pas activer RLS partout brutalement avant inventaire complet

---

## 4. Décisions d’architecture recommandées

## 4.1 Cible backend
Passer à un **modular monolith orienté domaines** :

- `identity_access`
- `country_module_control`
- `kyc_compliance`
- `wallet_ledger`
- `social_protection`
- `tasks_marketplace`
- `food_marketplace`
- `shop_marketplace`
- `subscriptions`
- `b2b`
- `tax_aml`
- `admin_support_accounting`

## 4.2 Cible base de données
Principe :
- tables additives
- pas de destruction immédiate
- colonnes de compatibilité tant que nécessaire
- migration en couches

## 4.3 Cible activation modules
Hiérarchie recommandée :
- module global
- continent
- pays
- ville optionnelle
- canal optionnel
- acteur optionnel

## 4.4 Cible rôles
Séparer :
- identité de connexion
- profils métier
- rôles
- permissions
- scopes

## 4.5 Cible comptabilité
Séparer :
- wallet utilisateur
- ledger comptable
- comptes de fonds
- rapprochement
- journaux fiscaux
- journaux AML

---

## 5. Priorités backend + migrations

Ordre recommandé.

## Priorité 0 — Stabilisation d’architecture
À faire avant tout gros nouveau domaine :
- document de référence
- inventaire des modèles actuels
- normalisation des conventions
- cartographie des routes
- décision claire `modular monolith` vs faux microservices

Statut :
- en cours via ce document

## Priorité 1 — IAM / RBAC / scopes
À faire maintenant.

Pourquoi :
- conditionne admin principal
- conditionne comptable par pays / continent
- conditionne restaurant staff
- conditionne support / KYC / modération

Backend / DB :
- tables rôles
- permissions
- assignations
- scopes
- invitations staff/admin
- endpoints de gestion staff

## Priorité 2 — Module control unifié
À faire tout de suite après.

Pourquoi :
- tu veux que tout existe mais soit activable/désactivable par admin
- pays, continent, food, VTC, shop, B2B doivent être pilotables sans code

Backend / DB :
- `platform_modules`
- `country_module_settings`
- `continent_module_settings`
- service de résolution d’activation
- endpoints admin principal

## Priorité 3 — Refondre le socle géographique
Pourquoi :
- pays oui, mais il faut demain continent / villes / zones
- food, diaspora, VTC, shop en dépendent

Backend / DB :
- `continents`
- `countries` enrichi sans casser l’existant
- `cities`
- `service_zones`
- rattachement modules / pricing / routing

## Priorité 4 — Food backend complet
Pourquoi :
- gros domaine demandé
- il impacte restaurant, livraison, diaspora, TVA, pricing

Backend / DB :
- restaurants
- menus
- commandes
- panier
- dispatch livraison
- split repas / livraison
- commission restaurant
- activation par pays

## Priorité 5 — Abonnements backend complet
Pourquoi :
- beaucoup de flux futurs s’appuient dessus

Backend / DB :
- plans
- abonnements
- wallet d’abonnement
- échéances
- prélèvements
- support ops

## Priorité 6 — Boutique / articles
Pourquoi :
- même infrastructure que food, mais autre catalogue et autres vendeurs

Backend / DB :
- marchands
- catalogue
- commandes
- livraison
- commission

## Priorité 7 — Fiscalité / TVA / B2B
Pourquoi :
- facture, comptabilité, abonnements, food, shop, diaspora

Backend / DB :
- tax profiles
- B2B / B2C
- VAT numbers
- tax ledger

## Priorité 8 — AML / conformité renforcée
Pourquoi :
- production + international + diaspora

Backend / DB :
- flags AML
- seuils
- cas
- reporting

## Priorité 9 — Litiges avancés
Pourquoi :
- FROZEN_AUDIT complet encore manquant

## Priorité 10 — VTC préparé mais inactif
Pourquoi :
- il faut préparer l’architecture sans l’ouvrir

## Priorité 11 — Interface / frontend
Seulement après socle backend solide.

---

## 6. Ce qu’on a déjà fait et qu’on conserve

À conserver et réutiliser :
- split social actuel
- overview social tasker
- notifications
- scheduler jobs
- logique KYC expiry
- route pays/admin rollout
- addresses utilisateur
- trust score / premiers badges
- service wallet / escrow
- social protection events

À ne pas casser :
- contrats API existants utiles
- migrations déjà livrées
- logique prod-safe existante

---

## 7. Ce qu’il faudra probablement écraser ou refondre

### À refondre progressivement
- `users.role` comme seule source de vérité des permissions
- activation modules dispersée entre flags et champs pays
- pays comme couche géographique unique
- compta uniquement dérivée des wallets métier

### À garder mais encapsuler
- wallet service
- KYC service
- trust service
- admin router

### À surveiller
- `countries.city` dans le modèle actuel
- cohérence des rôles métier
- compatibilité des types partagés web/admin
- dette TypeScript admin préexistante

---

## 8. Angles morts identifiés

Points non explicitement demandés mais nécessaires :

- versionning de configuration modules
- journal d’activation/désactivation de modules
- modèle d’invitation admin/staff
- reset mot de passe staff sécurisé
- découplage compte de connexion / profil métier
- catalogues multi-langues
- devise et taxe par commande figées au moment du checkout
- SLA et retry policy sur jobs critiques
- export comptable versionné
- mécanisme de suspension ciblée par module
- lecture restreinte des données comptables par scope
- audit des changements de pricing
- audit des changements de menu / catalogue
- gestion de disponibilité restaurant / vendeur / livreur
- mécanisme de feature rollout progressif
- stockage documentaire séparé par domaine sensible

---

## 9. Ce qu’on ne doit pas faire

- ne pas convertir brutalement le backend en microservices maintenant
- ne pas multiplier les champs booléens dans `countries` sans modèle de modules
- ne pas surcharger `tasks` pour faire `food`, `shop` et `vtc`
- ne pas utiliser un seul rôle texte pour tous les cas métier
- ne pas exposer les chiffres globaux à tous les admins
- ne pas mélanger ledger comptable et vue wallet utilisateur

---

## 10. Plan concret de prochain travail backend

### Phase A — architecture et migrations socles
1. créer le domaine IAM/RBAC/scopes
2. créer le registre de modules activables
3. créer la hiérarchie géographique continent/pays/ville/zone
4. brancher la résolution d’accès module par scope

### Phase B — domaines métier prioritaires
5. domaine restaurants + menus
6. domaine commandes food + livraison
7. domaine abonnements
8. domaine fiscalité B2B/B2C

### Phase C — contrôle et conformité
9. RBAC staff complet
10. AML renforcé
11. litiges avancés
12. préparation VTC inactive

### Phase D — interfaces
13. seulement après verrouillage backend/migrations

---

## 11. Priorité immédiate recommandée

La priorité immédiate n’est **pas** le frontend.

La priorité immédiate est :

1. **RBAC + scopes admin/staff**
2. **module control unifié**
3. **géographie / continent / zones**
4. **migrations food de base**

C’est le minimum pour être sur la bonne voie avant d’ajouter le reste.

---

## 12. Questions encore ouvertes

À confirmer plus tard, sans bloquer l’audit :

- nom officiel du module `shop/articles` : `SHOP`, `ARTICLES`, `GIFTS`, ou `MARKETPLACE`
- structure exacte des scopes comptables :
  - pays seul
  - continent seul
  - pays + module
  - continent + module
- commission restaurant exacte par marché
- politique finale de service fee non-abonné
- politique finale d’exonération TVA B2B
- niveau de RLS qu’on veut activer dès phase 1

---

## 13. Conclusion d’audit

Nous sommes **sur une base utile**, mais **pas encore sur l’architecture cible complète**.

Le backend actuel permet :
- d’avancer sans casser la prod
- de construire par couches
- de garder un chemin propre

Mais il manque encore les fondations centrales suivantes :
- RBAC scoppé
- module registry unifié
- géographie hiérarchique
- domaines backend food / subscriptions / shop / fiscalité / AML

La bonne voie est donc :
- **d’abord backend + migrations**
- **ensuite activation admin**
- **ensuite interfaces**

Ce fichier devient la référence de travail pour les prochains lots.

---

## 14. Implementation Update - 2026-06-06

### Backend lot completed today

- IAM / RBAC / scopes backend foundation is now in place.
- Legacy admin compatibility is preserved.
- Staff accounts can now be created by the principal admin with email + password.
- Staff roles and scopes can now be assigned from the backend.
- This is the first additive layer before module activation and geo hierarchy.

### Still missing in this domain

- admin invitations
- password reset flow for staff
- full route-by-route scope enforcement
- immutable audit log for RBAC changes
- richer scope hierarchy tied to modules, countries, continents and cities

### Backend lot completed today - module registry foundation

- A unified platform module registry now exists in backend and database.
- Module activation can now be resolved by `global -> continent -> country -> city` scope chain.
- The current implementation uses a safe country-to-continent mapping while waiting for the full geo hierarchy lot.
- `FOOD` remains synchronized with the legacy country boolean and legacy feature flag to avoid production drift.

### Backend lot completed today - geography hierarchy foundation

- A first persistent geo hierarchy now exists with continents, cities and service zones.
- The implementation is additive and keeps legacy country and city fields stable.
- Module activation is now ready to move from static continent mappings toward database-backed geography.
- This creates the right backend base for food, shop, transport and zone-scoped rollout.

### Backend lot completed today - accounting ledger foundation

- A first additive accounting ledger now exists in backend and database.
- Dedicated tables now exist for financial accounts, account scopes, ledger entries, fund transfers, reconciliation snapshots and country revenue snapshots.
- The accounting layer does not replace the operational wallet engine; it mirrors and consolidates it.
- System social-fund wallets can now be mirrored into dedicated accounting accounts.
- Tasker net distributions can now be mirrored into a synthetic distribution account for cleaner consolidation.
- Reconciliation snapshots can now compare accounting balances against operational wallet balances.
- Country revenue snapshots can now aggregate split totals by country, period and currency.

### Still missing in this domain

- automatic scheduler jobs for recurring ledger ingestion
- scoped accountant visibility by country and continent
- accounting postings for VAT, withdrawal fees and FX margin
- export-ready accounting reports and printable outputs

### Backend lot completed today - food domain foundation

- A first dedicated food backend domain now exists, separate from generic tasking.
- Restaurants, restaurant staff, menus, menu items, food orders and food order items are now first-class backend entities.
- The food runtime remains gated by the existing module-control layer, so the principal admin can keep the module off by country until launch.
- Food orders now store meal subtotal separately from delivery fee, which prepares the future split between restaurant payout and delivery payout.

### Still missing in this domain

- food payment and escrow lifecycle
- automatic creation of a delivery task after restaurant acceptance
- operational dispatch and delivery assignment
- stock, opening hours and temporary restaurant unavailability

### Backend lot completed today - food payment and dispatch foundation

- Food orders can now be funded from the backend with a real split between:
  - meal amount held for the restaurant
  - delivery amount locked in a dedicated delivery escrow
- Funding a food order now creates a linked `FOOD_DELIVERY` task automatically.
- The generic task engine remains responsible for the delivery mission itself.
- The food domain is now synchronized with the task domain at two critical points:
  - when a tasker accepts the linked delivery task
  - when the linked delivery task is confirmed complete
- This means the restaurant payout can now follow the confirmed delivery lifecycle instead of being hard-coded prematurely.

### Still missing in this domain

- service-zone aware dispatch ranking
- beneficiary OTP flows for diaspora food gifting
- restaurant inventory and temporary menu unavailability
- richer finance reporting on restaurant payouts

### Backend lot completed today - food operations and payout reporting foundation

- Restaurants can now be governed operationally with dedicated flags instead of full module shutdown only.
- Food now has a first stock-control layer for menu items.
- Food dispatch can now produce ranked candidate queues based on readiness and distance.
- Restaurant payout reporting can now be snapshotted per period and currency.
- This gives the admin a first backend foundation for:
  - operational pauses
  - sold-out handling
  - dispatch supervision
  - restaurant payout monitoring

### Still missing in this domain

- timezone-aware opening-hours enforcement
- strict geometry checks against stored service zones
- payout snapshot synchronization into accounting ledger
- richer restaurant catalog logic such as modifiers and combos

### Backend lot completed today - food catalog constraints and ledger sync foundation

- The food catalog now supports structured modifiers and paid options.
- Food availability is now checked against restaurant opening hours and item-level time windows.
- Restaurant delivery eligibility now has a first service-zone radius enforcement.
- Restaurant payout snapshots can now be mirrored into the accounting ledger foundation.

### Still missing in this domain

- polygon and multi-shape service-zone geometry
- holiday calendars and exceptional closures
- combo meals and nested catalog structures
- customer-side post-creation order editing flows

### Backend lot completed today - food combos, closures and payout-ledger sync foundation

- The food catalog now supports combo offers and combo composition.
- Restaurants can now block intake through exceptional closure windows, not only weekly schedules.
- Food orders can now be blocked by polygon-style service coverage when zone data is available.
- Restaurant payout reporting can now be pushed toward the accounting ledger foundation.

### Still missing in this domain

- higher-fidelity geospatial validation for complex delivery zones
- reusable holiday-calendar templates by country or city
- post-funding customer edit flows
- deeper merchandising and recommendation rules for bundles

### Backend lot completed today - notation bidirectionnelle et suspensions automatiques

- La couche de notation simple a �t� refondue en fondation bidirectionnelle m�tier.
- Le backend supporte maintenant deux directions publiques:
  - `TASKER_BY_CLIENT`
  - `CLIENT_BY_TASKER`
- Les agr�gats sont stock�s de mani�re compatible sur `users`:
  - `rating_sum` / `rating_count` pour la r�putation publique tasker,
  - `client_rating_sum` / `client_rating_count` pour la r�putation publique client.
- Les seuils automatiques sont branch�s:
  - tasker < 3.5/5 apr�s 10 reviews => suspension automatique,
  - client < 3/5 apr�s 5 reviews => restriction premium automatique.
- Les avis restent li�s � la t�che termin�e via `user_reviews`, avec unicit� par t�che et type d'avis.
- Le profil utilisateur expose d�sormais les deux faces de r�putation et les reviews r�centes.
- Le prochain lot naturel apr�s cette fondation est `referral` puis `subscriptions`.

### Backend lot completed today - subscriptions backend foundation

- Le backend supporte maintenant un vrai domaine `subscriptions` ind�pendant et extensible.
- Les plans peuvent �tre g�n�raux (`Zaska Pro`) ou sp�cifiques � une cat�gorie de service.
- Les quotas mensuels sont g�r�s c�t� backend avec consommation et quota restant.
- La cr�ation de t�che peut d�j� consommer un quota service si un abonnement compatible est actif.
- L�administration peut piloter les plans et attribuer des abonnements sans toucher au code.
- La couche est pr�te pour les prochaines extensions:
  - matching premium,
  - facturation r�elle des renouvellements,
  - savings analytics,
  - int�gration UI web/mobile/admin.

### Backend lot completed today - referral backend foundation

- Le backend supporte maintenant un vrai domaine `referral` distinct et extensible.
- Chaque utilisateur peut avoir un code de parrainage unique.
- Un utilisateur inscrit peut �tre rattach� � un parrain d�s l�inscription.
- Les deux sc�narios produits sont couverts c�t� backend:
  - client filleul -> qualification � la premi�re commande,
  - tasker filleul -> qualification au 10e job compl�t�.
- Les r�compenses peuvent �tre:
  - cr�dit wallet imm�diat,
  - cr�dit plateforme conserv� pour usage futur.
- L�administration peut lire et ajuster les programmes sans toucher au code.
- Cette fondation pr�pare directement:
  - affichage UI du parrainage,
  - application du cr�dit sur souscriptions/commandes,
  - analytics d�acquisition par march�.
