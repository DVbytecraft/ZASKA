# ZASKA BACKEND PRODUCTION READY CHECKLIST

Date: 2026-06-07  
Statut: Référence de verrouillage final backend

---

## 1. Règle de vérité

Le backend ne doit être qualifié **PRODUCTION READY** que si les 5 blocs suivants sont validés :

- **A. Schéma et migrations**
- **B. Flux métier critiques**
- **C. Intégrations externes réelles**
- **D. Exploitation / observabilité / reprise**
- **E. Validation réelle en environnement**

Tant qu’un de ces blocs reste incomplet, on parle de **backend avancé**, pas de backend définitivement prêt production.

---

## 2. État actuel honnête

### Déjà solide

- RBAC / scopes / modules / géographie
- social protection / split / fonds
- disputes / AML / KYC avancé fondation
- subscriptions / referral / B2B
- VTC backend opérationnel
- SHOP backend opérationnel
- FOOD backend opérationnel
- scheduler / workers / health endpoints
- cycle de résilience transverse

### Pas encore totalement verrouillé

- tests d’exécution end-to-end
- tests de charge / concurrence
- migrations testées sur vraie base cible
- vérification runtime complète des workers
- intégrations providers réelles encore simulées sur certains volets
- runbooks d’exploitation et reprise
- alerting métier / ops assez fin

---

## 3. GATES obligatoires

## A. Schéma et migrations

### Obligatoire

- toutes les migrations Alembic s’appliquent proprement depuis un environnement vide
- toutes les migrations s’appliquent proprement depuis un dump/staging proche prod
- aucune migration ne casse les données existantes
- indexes critiques présents sur:
  - tasks
  - rides
  - orders
  - escrows
  - holds
  - reviews
  - aml / kyc / disputes
- contraintes FK cohérentes
- rollback ou plan de restauration documenté

### État

- **Partiellement fait**

### À faire

- test complet de chaîne Alembic
- audit index/performance
- validation de volume réel

---

## B. Flux métier critiques

### Obligatoire

- VTC:
  - création course
  - dispatch
  - accept/reject
  - en route
  - arrivé
  - démarrage
  - fin
  - payout chauffeur
- SHOP:
  - création commande
  - funding
  - confirmation marchand
  - préparation
  - livraison
  - finalisation
  - payout marchand
- FOOD:
  - création commande
  - funding
  - confirmation restaurant
  - préparation
  - dispatch livraison
  - livraison
  - payout restaurant
- TASK marketplace:
  - création
  - acceptation
  - completion
  - validation OTP / auto validation
  - split wallet
- compliance:
  - KYC gating
  - AML hold/review
  - dispute freeze/release/refund

### État

- **Code backend très avancé**
- **Validation réelle non encore certifiée**

### À faire

- tests scénarisés par module
- tests d’erreurs métier
- tests d’idempotence

---

## C. Intégrations externes réelles

### Obligatoire

- paiement provider réel
- webhooks paiement réellement validés
- OTP provider réel
- email provider réel
- push provider réel
- OCR/KYC provider réel ou procédure manuelle formalisée
- AML reporting réel si requis

### État

- **Mixte**

### Risque

- c’est le principal point qui empêche de déclarer “production ready total” aujourd’hui sans réserve

### À faire

- lister provider par domaine
- marquer:
  - branché réel
  - mock
  - fallback manuel

---

## D. Exploitation / observabilité / reprise

### Obligatoire

- health checks complets
- métriques exploitables
- logs structurés
- watchdog scheduler
- alertes jobs silencieux
- backup base
- restauration testée
- surveillance queues / outbox / payout / disputes / KYC
- runbook incident

### État

- **Bien avancé**

### À faire

- enrichir alertes métiers
- vérifier dead-letter/retry par domaine
- documenter runbooks

---

## E. Validation réelle en environnement

### Obligatoire

- staging branché comme la prod
- migration de staging réussie
- démarrage API réussi
- démarrage workers réussi
- jobs scheduler validés
- scénarios E2E validés
- test charge minimal
- test concurrence minimal
- smoke test post-deploy

### État

- **Pas encore certifié**

### À faire

- exécuter la campagne de validation backend

---

## 4. Blocages restants pour pouvoir dire “backend production ready”

### Blocage 1 — Validation runtime réelle
- aujourd’hui on a surtout validé par structure et compilation ciblée
- il faut maintenant valider par exécution réelle

### Blocage 2 — Providers externes
- certains volets sont encore provider-agnostic / simulés
- il faut les fermer ou documenter leur fallback d’exploitation

### Blocage 3 — Campagne de tests métier
- il manque la campagne de certification flux critiques

### Blocage 4 — Campagne de charge / concurrence
- surtout pour wallet, escrows, payouts, dispatch

---

## 5. Ce qu’il faut faire maintenant

## Phase P1 — Certification technique

- appliquer les migrations
- démarrer API
- démarrer workers
- valider imports / scheduler / routes critiques
- vérifier health endpoints

## Phase P2 — Certification métier

- exécuter scénarios critiques:
  - task classique
  - food
  - shop
  - vtc
  - dispute
  - aml
  - kyc
  - payout

## Phase P3 — Certification exploitation

- simuler incidents simples
- vérifier backup / restore
- vérifier watchdog / health / metrics

## Phase P4 — Fermeture des derniers gaps

- providers réels manquants
- alertes métiers
- docs runbook

---

## 6. Décision honnête

### Aujourd’hui

Le backend est :

- **architecturé sérieusement**
- **très avancé**
- **proche d’un vrai niveau prod**

Mais je ne dois pas encore dire :

- “100% production ready final”

tant que la **campagne de certification réelle** n’a pas été exécutée.

---

## 7. Définition de fin

On pourra dire **backend production ready** quand :

- toutes les migrations passent
- tous les services démarrent
- tous les flux critiques passent en staging
- les workers tournent proprement
- les health checks sont verts
- les providers requis sont réellement branchés ou officiellement fallbackés
- les scénarios critiques sont validés

---

## 8. Prochaine action recommandée

La prochaine phase n’est plus une phase de design.

La prochaine phase doit être :

- **campagne de certification backend**

avec cet ordre :

1. migrations
2. démarrage backend
3. smoke tests
4. scénarios critiques
5. revue des derniers gaps

