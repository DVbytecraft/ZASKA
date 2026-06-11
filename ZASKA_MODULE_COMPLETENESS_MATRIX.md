# ZASKA MODULE COMPLETENESS MATRIX

Date: 2026-06-07  
Statut: Document de pilotage vivant  
Objectif: cartographier, sans bricolage, l’état réel de chaque module Zaska, ce qui existe déjà, ce qui manque encore côté backend et côté interfaces, et l’ordre de priorité pour atteindre un niveau production-ready.

---

## 1. Légende des statuts

- `READY_FOUNDATION` : la base technique et métier est solide, mais le module n’est pas encore un produit fini.
- `PARTIAL_OPERATIONAL` : plusieurs flux existent déjà, mais le module n’est pas encore complet pour un go-live sans réserve.
- `NEAR_PRODUCTION` : le module est proche d’un usage réel, mais il manque des briques critiques.
- `PRODUCTION_READY` : backend, contrôles, opérations, interfaces et observabilité sont jugés suffisants pour un déploiement maîtrisé.

Important: au 2026-06-07, **le socle plateforme est avancé**, mais les modules `FOOD`, `SHOP`, `VTC` et plusieurs expériences métier ne sont **pas encore `PRODUCTION_READY` en totalité**.

---

## 2. Vue d’ensemble

| Domaine | Statut actuel | Côté 1 | Côté 2 | Admin/Ops | Blocage principal |
|---|---|---|---|---|---|
| Core Marketplace / Tasks | PARTIAL_OPERATIONAL | Client | Tasker | Oui | matching premium, modération temps réel, UX complète |
| Social Protection | PARTIAL_OPERATIONAL | Tasker | — | Oui | automatisations et restitution UI complète |
| Wallet / Ledger / Accounting | PARTIAL_OPERATIONAL | Utilisateur | — | Oui | postings exhaustifs, exports finals, reconciliation externe |
| KYC / AML / Compliance | PARTIAL_OPERATIONAL | Utilisateur | Admin KYC/AML | Oui | providers réels OCR/NLP/biometric/reporting |
| Disputes | PARTIAL_OPERATIONAL | Client/Tasker | Agent | Oui | UI agent complète, SLA outillage, preuves UX |
| Subscriptions | READY_FOUNDATION | Client | — | Oui | billing réel, renewals, économies, premium gating complet |
| Referral | READY_FOUNDATION | Parrain | Filleul | Oui | application réelle des crédits au checkout |
| B2B | READY_FOUNDATION | Entreprise | Staff entreprise | Oui | facturation, UI complète, matching et rapports complets |
| FOOD | PARTIAL_OPERATIONAL | Client | Restaurant | Oui | UX complète, dispatch live, payouts finaux, support ops |
| SHOP | PARTIAL_OPERATIONAL | Client | Marchand | Oui | interfaces finales, gifting complet, observabilité ops |
| VTC | PARTIAL_OPERATIONAL | Client | Chauffeur | Oui | interfaces finales, observabilité live, dispatch tuning |
| Module Control / Geography / RBAC | PARTIAL_OPERATIONAL | — | — | Oui | enforcement global final et UI admin de pilotage complète |

---

## 3. Socle transversal déjà présent

### 3.1 Fondations disponibles

- RBAC additif admin/staff
- scopes pays / continent / module
- registre modules activables/désactivables
- hiérarchie géographique persistante
- pays activables par l’admin sans code
- wallet utilisateur
- ledger comptable additif
- split social tasker
- protection sociale tasker
- notifications backend
- KYC avancé fondation
- AML fondation
- disputes avancés fondation
- B2B fondation
- food/shop/vtc fondations backend

### 3.2 Chantiers transverses encore obligatoires

Ces points concernent **tous les modules** et doivent être considérés comme des prérequis à un vrai `PRODUCTION_READY` :

- websockets / push temps réel centralisés
- journal d’audit plus exhaustif sur tous les modules
- observabilité: métriques, traces, alertes
- stratégie retry / idempotence / dead-letter jobs
- tests métier automatisés par domaine
- tests de concurrence, tests de charge, tests financiers
- sauvegarde / restauration / disaster recovery
- stockage documentaire sécurisé par domaine
- versionning des réglages admin
- règles de rétention / anonymisation / privacy
- intégrations providers réelles là où encore simulées
- cycle de résilience opérationnelle transverse déjà ajouté pour VTC / SHOP / FOOD

---

## 4. Module Core Marketplace / Tasks

### 4.1 Client

#### Déjà présent
- création de tâches
- pays/zone contrôlés
- urgences partiellement préparées
- OTP / validation / auto-validation fondation
- historique tâche
- notation fondation

#### Manques backend
- moteur premium complet par abonnement
- règles urgentes exhaustives sur pricing, matching et priorisation
- détection frauduleuse message temps réel complète
- contrôle de cohérence géographique plus poussé
- workflow “commande pour quelqu’un d’autre” totalement industrialisé
- moteur de sélection tasker plus fin

#### Interfaces nécessaires
- création de tâche complète avec pays/zone/catégorie intelligents
- suivi live de la tâche
- validation OTP claire
- contestation litige native
- notation multi-critères complète
- centre d’abonnements / économies réalisées

### 4.2 Tasker

#### Déjà présent
- sécurité tasker renforcée
- split social et capital social
- dashboard social
- notes tasker

#### Manques backend
- matching avancé
- règles premium/tasker senior/top rated dans l’affectation
- contrôle KYC expiré bloquant tous les points d’entrée métier
- alertes opérationnelles plus fines
- performance scoring plus riche

#### Interfaces nécessaires
- feed de tâches plus intelligent
- filtres premium / urgent / proximité
- workflow acceptation / arrivée / début / fin plus clair
- centre d’alertes actionnables
- reporting gains / performance / conformité

### 4.3 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`
- **Pour passer production-ready**:
  - finaliser matching
  - finaliser workflow urgent
  - finaliser diaspora end-to-end
  - finaliser gating premium
  - finaliser UX temps réel

---

## 5. Module Social Protection

### 5.1 Côté Tasker

#### Déjà présent
- split 77.5 / 8 / 7 / 5 / 2.5
- historique des splits
- dashboard capital social
- moteur lissage fondation
- badges sociaux fondation

#### Manques backend
- projections actuarielles plus robustes
- versements santé autorité par pays
- intérêts simulés plus industrialisés
- reporting mensuel par pays plus complet
- règles avancées de pension garantie

#### Interfaces nécessaires
- meilleure visualisation pension / santé / lissage
- historique exportable
- explications pédagogiques pour le tasker
- indicateurs d’éligibilité et d’avancement

### 5.2 Admin / Comptable

#### Déjà présent
- lecture comptable de base
- dashboards sociaux partiels

#### Manques backend
- rapprochement bancaire externe
- exports standardisés
- vues pays/continent/rôle plus fines
- alertes de solde social

#### Interfaces nécessaires
- cockpit comptable social complet
- exports PDF/Excel
- drill-down par pays, ville, fonds, période

### 5.3 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`

---

## 6. Module Wallet / Accounting / Finance

### 6.1 Utilisateurs

#### Déjà présent
- wallet tasker
- retraits fondation
- historique partiel
- ledger additif

#### Manques backend
- frais de retrait exhaustifs et paramétrables
- postings comptables exhaustifs par type d’opération
- flux multi-devises consolidés
- gestion crédits referral / subscription réellement consommables partout
- rapprochement paiement provider ↔ ledger ↔ wallet

#### Interfaces nécessaires
- wallet complet par profil
- détail ligne à ligne de toutes les écritures
- état retraits / refus / pending
- visibilité crédits et soldes séparés

### 6.2 Comptables / Admin

#### Déjà présent
- base ledger
- snapshots de revenus
- quelques vues comptables

#### Manques backend
- TVA complète par pays
- marge FX complète
- reports fiscaux autorité
- exports comptables normés
- multi-entités comptables selon pays/continent

#### Interfaces nécessaires
- grand livre
- balance simplifiée
- journal des revenus
- exports fiscaux
- dashboard multi-zone

### 6.3 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`

---

## 7. Module KYC / AML / Compliance

### 7.1 Utilisateurs

#### Déjà présent
- KYC avancé fondation
- casier judiciaire modélisé
- biométrie KYC modélisée
- AML cases modélisées

#### Manques backend
- vrai provider OCR
- vrai provider biométrie / liveness
- vrai provider casier / NLP si applicable
- reporting réglementaire réel par pays
- règles de blocage / déblocage plus exhaustives
- gestion documentaire sécurisée avec rotation / conservation

#### Interfaces nécessaires
- onboarding KYC complet
- renouvellement simplifié
- statuts clairs de dossier
- relances et corrections guidées

### 7.2 Admin KYC / AML

#### Déjà présent
- review de base
- cas AML
- endpoints admin

#### Manques backend
- queues de traitement par agent
- SLA / aging / escalade supervisée
- score de risque configurable
- reporting autorité final

#### Interfaces nécessaires
- centre KYC complet
- centre AML complet
- lecture document / comparaison
- décisions tracées

### 7.3 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`

---

## 8. Module Disputes

### 8.1 Client / Tasker

#### Déjà présent
- contestation
- gel `FROZEN_AUDIT`
- ticket enrichi

#### Manques backend
- pièces jointes plus industrialisées
- timelines enrichies
- templates de résolution
- SLA automatiques plus complets

#### Interfaces nécessaires
- écran “Contester”
- timeline du litige
- upload de preuves
- statuts compréhensibles

### 8.2 Agent / Admin

#### Déjà présent
- listing
- détail
- assignation
- note
- escalade
- décision release/refund/partial_refund

#### Manques backend
- priorisation plus intelligente
- files d’attente par agent/pays
- macros décisionnelles
- mesures de performance des agents

#### Interfaces nécessaires
- vrai centre agent
- panel d’historique complet
- filtres avancés
- exports et supervision SLA

### 8.3 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`

---

## 9. Module Subscriptions

### 9.1 Client

#### Déjà présent
- plans généraux et par service
- activation / pause / reprise / annulation
- quotas

#### Manques backend
- billing réel avec provider
- renouvellement automatique réel
- gestion échec paiement
- calcul économies mensuelles exact
- consommation plus fine selon service
- gating premium robuste partout

#### Interfaces nécessaires
- catalogue d’abonnements
- souscription simple
- suivi des quotas
- économie réalisée
- upgrade / downgrade

### 9.2 Admin

#### Déjà présent
- gestion des plans côté API

#### Manques backend
- métriques churn / conversion / MRR plus robustes
- segmentation pays/continent

#### Interfaces nécessaires
- console plans et promotions
- analytics abonnements

### 9.3 Statut
- **Statut actuel**: `READY_FOUNDATION`

---

## 10. Module Referral

### 10.1 Utilisateurs

#### Déjà présent
- codes uniques
- qualification client / tasker
- récompenses wallet / crédit

#### Manques backend
- application automatique des crédits à l’achat
- règles marketing plus souples par pays
- anti-abus referral plus poussé

#### Interfaces nécessaires
- écran de parrainage
- suivi filleuls / gains
- rappel de progression

### 10.2 Admin

#### Déjà présent
- base programme

#### Manques backend
- dashboards de performance
- contrôles anti-fraude spécifiques

#### Interfaces nécessaires
- configuration programme
- rapports par pays / campagne

### 10.3 Statut
- **Statut actuel**: `READY_FOUNDATION`

---

## 11. Module FOOD

### 11.1 Client Food

#### Déjà présent
- consultation restaurants / menus
- commande food backend
- total repas + livraison
- dispatch fondation
- historique client runtime
- détail commande runtime

#### Manques backend
- panier multi-restaurant (si voulu) ou règle d’unicité stricte
- codes promo / campagnes
- ETA fiable
- annulation client contrôlée
- substitutions article
- gifting / diaspora food complet
- paiement provider finalisé bout en bout
- push live de statut commande

#### Interfaces nécessaires
- home food
- fiche restaurant
- menu détaillé
- panier
- checkout
- suivi commande live
- support / annulation / litige

### 11.2 Restaurant

#### Déjà présent
- compte restaurant
- staff restaurant
- menus
- articles
- modifiers
- combos
- closures
- stock de base
- payouts snapshots
- historique commandes runtime
- consultation payouts runtime
- sync payouts vers comptabilité runtime

#### Manques backend
- workflow acceptation/refus commande restaurant
- SLA préparation
- substitutions / indisponibilités de dernière minute
- taxation restaurant plus fine
- settlement réel vers restaurant
- gestion horaires avancés et timezone complète
- staffing / rôles restaurant fins

#### Interfaces nécessaires
- dashboard restaurant
- écran commandes en attente / en cours / terminées
- gestion menu / stock / modifiers / combos
- gestion horaires / fermetures
- reporting payouts

### 11.3 Livreur / Tasker Food

#### Déjà présent
- création tâche `FOOD_DELIVERY`
- escrow livraison

#### Manques backend
- dispatch live
- accept/reject livraison
- navigation statuts pickup / picked / en route / delivered
- preuve de remise
- réassignation automatique

#### Interfaces nécessaires
- feed livraison food dédié
- carte pickup/dropoff
- statuts course food
- preuve de livraison

### 11.4 Admin / Ops Food

#### Déjà présent
- création / gestion restaurants
- gestion catalogues food
- base reporting payouts

#### Manques backend
- settlement ops
- monitoring dispatch
- console incidents restaurant
- analytics food par ville / pays / restaurant

#### Interfaces nécessaires
- console opérations food
- supervision commandes
- analytics restaurants
- outils de suspension ciblée

### 11.5 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`
- **Pour passer production-ready**:
  - workflow restaurant complet
  - dispatch live complet
  - payouts finaux
  - UX client/livreur/restaurant complète
  - observabilité ops food

---

## 12. Module SHOP / ARTICLES

### 12.1 Client Shop

#### Déjà présent
- catalogues
- articles
- commandes
- stock décrémenté
- financement commande
- livraison liée à une tâche
- suivi d’événements backend

#### Manques backend
- panier plus riche
- gifting/diaspora complet
- livraison / fulfillment
- annulations / retours / remboursements
- paiement finalisé
- promotions / coupons
- variantes article / SKU avancés

#### Interfaces nécessaires
- home shop
- catalogue
- fiche article
- panier
- checkout
- suivi commande
- retours / assistance

### 12.2 Marchand

#### Déjà présent
- compte marchand
- staff marchand
- catalogues
- articles
- dashboard de base
- workflow `accepted / preparing / ready / delivered / cancelled`
- snapshots de payouts backend

#### Manques backend
- fulfilment
- préparation / packing
- rupture dynamique
- variantes / attributs / SKU
- pricing promo
- payout marchand réel

#### Interfaces nécessaires
- console marchand
- gestion catalogue / stock
- gestion commandes
- reporting ventes / payouts

### 12.3 Livraison / Tasker Shop

#### Déjà présent
- tâche `SHOP_DELIVERY` créée au funding
- assignation livraison synchronisée
- finalisation commande reliée à la tâche

#### Manques backend
- création tâche livraison shop
- dispatch
- statuts fulfillment
- preuve de remise

#### Interfaces nécessaires
- feed livraison shop
- parcours collecte / remise

### 12.4 Admin / Ops Shop

#### Déjà présent
- gestion marchands et catalogues
- détail commande
- financement admin
- pilotage statut
- génération payouts

#### Manques backend
- ops fulfilment
- settlement marchand
- analytics stock / ventes
- contrôle qualité catalogue

#### Interfaces nécessaires
- console operations shop
- review catalogues
- supervision commandes

### 12.5 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`
- **Pour passer production-ready**:
  - interfaces client/marchand complètes
  - gifting / diaspora articles complet
  - observabilité et outillage ops fulfilment
  - QA métier complète

---

## 13. Module VTC

### 13.1 Client VTC

#### Déjà présent
- création demande de course
- devis et quote backend
- dispatch d’offres chauffeur
- historique de base
- annulation client

#### Manques backend
- calcul prix / estimation
- dispatch temps réel
- affectation chauffeur
- annulation contrôlée
- paiement ride complet
- partage de course / sécurité
- support temps réel

#### Interfaces nécessaires
- home VTC
- saisie pickup / destination
- estimation prix / ETA
- recherche chauffeur
- suivi live de course
- paiement / reçu

### 13.2 Chauffeur / Prestataire

#### Déjà présent
- compte chauffeur
- profil chauffeur
- véhicule
- dashboard base
- présence online/offline
- réception d’offres
- accept / reject
- cycle `en route / arrivé / démarré / terminé`
- géolocalisation live backend
- payout chauffeur backend

#### Manques backend
- disponibilité online/offline
- réception d’appel de course
- accept / reject
- arrivée / démarrage / fin course
- géolocalisation live
- preuve de course
- revenus course / payout chauffeur
- contrôle documents véhicule/permis plus poussé

#### Interfaces nécessaires
- app chauffeur
- incoming ride request
- navigation états course
- revenus / historique
- conformité véhicule/documents

### 13.3 Opérateur / Flotte

#### Déjà présent
- opérateur de flotte

#### Manques backend
- assignation chauffeurs à flotte
- supervision flotte
- performance et revenus par flotte

#### Interfaces nécessaires
- console flotte
- gestion chauffeurs / véhicules
- supervision courses

### 13.4 Admin / Ops VTC

#### Déjà présent
- création chauffeurs / véhicules / courses via admin
- détail course
- redispatch manuel
- assignation manuelle chauffeur
- règlement manuel payout

#### Manques backend
- dispatch ops
- pricing dynamique
- safety ops
- incidents et support ride
- analytics mobilité

#### Interfaces nécessaires
- centre ops VTC
- supervision live
- contrôle incidents

### 13.5 Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`
- **Pour passer production-ready**:
  - interfaces client/chauffeur/flotte
  - tuning pricing réel par marché
  - observabilité et alertes ops
  - websocket/push temps réel
  - QA métier complète

---

## 14. Module B2B

### 14.1 Entreprise

#### Déjà présent
- organisation
- membres
- contrats
- templates
- work orders

#### Manques backend
- facturation mensuelle réelle
- quotas et dépassements monétaires
- approbations internes entreprise
- reporting SLA entreprise

#### Interfaces nécessaires
- dashboard entreprise
- gestion contrats
- gestion commandes / tâches
- reporting activité

### 14.2 Staff entreprise

#### Déjà présent
- memberships fondation

#### Manques backend
- rôles internes entreprise plus fins
- séparation approbateur / opérateur / viewer

#### Interfaces nécessaires
- espace staff
- permissions par rôle

### 14.3 Admin B2B

#### Déjà présent
- création et pilotage via API

#### Manques backend
- analytics revenus entreprise
- contrôle contrats avancé
- exports plus fins

#### Interfaces nécessaires
- centre B2B admin

### 14.4 Statut
- **Statut actuel**: `READY_FOUNDATION`

---

## 15. Module Admin Global

### Déjà présent
- RBAC fondation
- scopes pays/continent/module
- nombreuses routes admin
- pays/modules activables

### Manques backend
- enforcement scope sur 100% des endpoints historiques
- rôles staff encore plus fins par domaine
- versioning de configuration admin
- workflow invitation / reset / onboarding staff plus complet

### Interfaces nécessaires
- cockpit admin principal
- gestion staff
- gestion rôles/scopes
- gestion modules
- gestion pays/continents/villes/zones
- supervision multi-modules

### Statut
- **Statut actuel**: `PARTIAL_OPERATIONAL`

---

## 16. Priorité production recommandée

### Priorité 1 — Clore les manques critiques backend

1. `VTC operational backend`
   - dispatch
   - accept/reject
   - cycle ride complet
   - pricing
   - payout chauffeur

2. `SHOP operational backend`
   - fulfilment
   - livraison
   - payout marchand
   - retours/remboursements

3. `FOOD completion backend`
   - workflow restaurant complet
   - dispatch temps réel
   - settlement restaurant final

4. `Cross-cutting reliability`
   - realtime notifications
   - retries
   - observability
   - tests métier
   - idempotence partout

### Priorité 2 — Completer les interfaces métier

1. restaurant
2. client food
3. chauffeur VTC
4. client VTC
5. marchand
6. client shop
7. admin ops

### Priorité 3 — Durcir l’exploitation

- analytics
- exports finaux
- supervision support
- conformité renforcée

---

## 17. Définition stricte d’un module `PRODUCTION_READY`

Un module n’est considéré `PRODUCTION_READY` que si les points suivants sont tous vrais :

- modèle de données stabilisé
- migrations testées
- permissions et scopes finalisés
- workflows métier complets
- paiements et settlements fiables
- contrôles fraude / KYC / AML reliés
- journaux d’audit suffisants
- monitoring / alerting en place
- retries / idempotence gérés
- interfaces principales disponibles
- tests métier critiques en place
- documentation d’exploitation disponible

---

## 18. Ordre d’exécution recommandé à partir d’ici

### Backend

1. compléter `VTC`
2. compléter `SHOP`
3. compléter `FOOD`
4. renforcer `realtime + observability + reliability`
5. fermer les derniers trous `admin scope + finance + compliance`

### Interfaces

1. admin principal
2. restaurant
3. client food
4. chauffeur VTC
5. client VTC
6. marchand shop
7. client shop
8. entreprise B2B

---

## 19. Conclusion honnête

Le backend Zaska a désormais **une base sérieuse, structurée et scalable**.  
Mais si l’objectif est “chaque module complet des deux côtés, backend prêt production, puis interfaces nécessaires”, alors **il reste encore du travail important sur `FOOD`, `SHOP`, `VTC` et plusieurs flux transverses**.

La bonne nouvelle: nous savons maintenant précisément **où nous en sommes**, **ce qui manque**, et **dans quel ordre le faire proprement**.
