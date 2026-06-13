# ZASKA Current State Audit

Date: 2026-06-13

## 1. État global

Le repo est presque propre:

- seul fichier non suivi vu pendant l’audit:
  - `backup_before_reset.sql`

Conclusion:

- pas de dérive Git massive visible au moment de l’audit
- la base de travail reste exploitable

## 2. Niveau actuel

### Backend

Le backend est à un niveau avancé sur le plan structurel:

- compilation ciblée Python OK
- grands modules présents:
  - tasks
  - wallets
  - social protection
  - food
  - shop
  - vtc
  - kyc
  - aml
  - disputes
  - b2b
  - pricing
  - geo/countries

Mais la validation automatisée n’est pas encore suffisamment industrialisée.

### Frontend web

Le frontend web principal est déjà à un niveau utilisable:

- `npm run typecheck` OK
- `npm run build` OK

Donc:

- le bundle web client compile
- les pages nouvellement branchées ne cassent pas la build Vite

### Frontend admin

Le frontend admin a évolué, mais il n’a pas encore sa propre chaîne de validation explicite:

- pas de script de build/typecheck dédié clairement exposé dans le monorepo
- il faut encore l’industrialiser

### Mobile

Le mobile existe, mais l’audit montre une faiblesse process:

- `apps/mobile/package.json` n’expose que:
  - `start`
  - `android`
  - `ios`

Il manque au minimum:

- typecheck
- lint
- éventuellement build/check Expo selon le workflow choisi

## 3. Résultats des contrôles lancés

### Git

- `git status --short`
  - seulement `?? backup_before_reset.sql`

### Frontend web

- `npm run typecheck`
  - OK

- `npm run build`
  - OK

- `npm run lint`
  - KO

#### Nature des erreurs lint

Le lint web ne révèle pas une app “cassée” au build, mais une qualité frontend encore incomplète:

1. environnement navigateur mal déclaré dans ESLint
   - `localStorage`
   - `window`
   - `document`
   - `fetch`
   - `URL`
   - `URLSearchParams`
   - `WebSocket`
   - `RequestInit`
   - `confirm`
   - `setTimeout`

2. hooks React à fiabiliser
   - dépendances `useEffect` manquantes sur plusieurs pages

3. quelques dettes locales
   - `React` non importé sur un fichier
   - `Balance` inutilisé dans `WalletPage`
   - `any` résiduel dans `ChatPage`

Conclusion:

- le frontend web fonctionne au build
- mais il n’est pas encore propre au niveau qualité/lint

### Backend

- `python -m py_compile` ciblé
  - OK

- `python -m scripts.backend_readiness_audit`
  - KO sans environnement

- `python -m pytest -q`
  - KO dès la collecte

#### Cause principale backend

La cause racine n’est pas un bug métier immédiat, mais un problème de validation/configuration:

- `DATABASE_URL is required`

Conséquences:

- l’audit backend ne peut pas s’exécuter sans env chargé
- la suite de tests backend ne peut même pas collecter les tests
- beaucoup de modules importent `Settings()` trop tôt pour le mode test actuel

#### Problèmes additionnels détectés

- warnings `.pytest_cache` en accès refusé
- dépendance forte à l’environnement pour les tests

Conclusion:

- le backend n’est pas “cassé” à la compilation
- mais sa testabilité locale/staging reste insuffisamment préparée

## 4. Insuffisances réelles identifiées

### A. Qualité frontend web

À corriger:

- config ESLint navigateur
- dépendances `useEffect`
- nettoyage petits warnings/legacy

### B. Testabilité backend

À corriger:

- charger un env de test/certification automatiquement pour les tests
- éviter que l’import global de `Settings()` bloque toute la collecte
- rendre `pytest` exécutable sans bricolage manuel

### C. Industrialisation admin

À corriger:

- outillage dédié build/typecheck/lint pour la surface admin

### D. Industrialisation mobile

À corriger:

- scripts validation mobile
- stratégie de contrôle minimum Expo/TypeScript/lint

## 5. Comment voir les bugs et insuffisances de façon fiable

À partir de maintenant, la bonne méthode pour “voir ce qui ne va pas” est:

1. Git
   - `git status --short`

2. Web client
   - `npm run typecheck --workspace @zaska/web`
   - `npm run build --workspace @zaska/web`
   - `npm run lint --workspace @zaska/web`

3. Backend
   - `python -m py_compile ...`
   - `python -m scripts.backend_readiness_audit`
   - `python -m pytest -q`

4. Certification runtime
   - `python backend/fastapi/scripts/run_backend_certification.py ...`

5. Vérification fonctionnelle
   - lancer backend
   - lancer web
   - tester les parcours:
     - auth
     - pays
     - marketplace
     - food
     - shop
     - vtc
     - tasks
     - wallet
     - admin

## 6. Verdict honnête

### Ce qui est déjà bien

- architecture large déjà en place
- backend riche fonctionnellement
- frontend web buildable
- nouveaux modules visibles
- géo/pays/pricing déjà branchés

### Ce qui n’est pas encore fini

- qualité lint frontend
- testabilité backend sans env manuel
- validation outillée admin
- validation outillée mobile
- campagne fonctionnelle bout-en-bout systématique

## 7. Priorité recommandée pour terminer l’application

### Phase 1 — Assainir la base

1. corriger le lint web
2. rendre les tests backend exécutables avec un env test standard
3. ajouter une validation admin
4. ajouter une validation mobile

### Phase 2 — Vérification fonctionnelle

5. ouvrir l’app et tester tous les flux simulés
6. noter les bugs UX, API, état, routage, permissions, pricing

### Phase 3 — Finition produit

7. corriger bugs fonctionnels
8. améliorer UX premium module par module
9. compléter les trous restants
10. refaire une campagne de validation complète

## 8. Niveau actuel en une phrase

Le projet est à un niveau “fort en architecture et déjà démontrable”, mais pas encore au niveau “terminé, proprement validé et verrouillé” tant que la qualité frontend, la testabilité backend et la validation multi-surfaces ne sont pas refermées.
