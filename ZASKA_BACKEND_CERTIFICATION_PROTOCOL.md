# ZASKA BACKEND CERTIFICATION PROTOCOL

Date: 2026-06-07  
Objectif: certifier le backend Zaska sans toucher à la production  
Mode: **non destructif d’abord**, puis staging contrôlé

---

## 1. Règle absolue

Ne jamais lancer ce protocole directement contre la base de production sans validation explicite.

Ordre obligatoire:

1. **audit statique**
2. **environnement de certification isolé**
3. **migrations sur base clonée / staging**
4. **démarrage backend**
5. **health checks**
6. **scénarios critiques**
7. **revue des écarts**

---

## 2. Préparation

## 2.1 Créer un environnement de certification

Préparer un fichier d’environnement séparé, par exemple:

- `backend/fastapi/.env.certification`

Il doit pointer vers:

- une base de staging ou une copie/restauration récente de prod
- un Redis de staging
- des secrets dédiés staging
- des providers sandbox/test

Variables minimales à vérifier:

- `ENV=development` ou `ENV=staging` selon votre convention
- `PAYMENT_MODE=sandbox`
- `DATABASE_URL=<base_staging>`
- `REDIS_URL=<redis_staging>`
- `CELERY_BROKER_URL=<redis_staging_broker>`
- `CELERY_RESULT_BACKEND=<redis_staging_backend>`
- `JWT_SECRET=<secret_long>`
- `ZASKA_WALLET_USER_ID=<wallet_systeme_staging>`
- `PENSION_FUND_USER_ID=<id_staging>`
- `HEALTH_FUND_USER_ID=<id_staging>`
- `SMOOTHING_FUND_USER_ID=<id_staging>`
- `STRIPE_SECRET_KEY=<sk_test_...>` si Stripe est utilisé
- `FEDAPAY_API_KEY=<sandbox...>` si FedaPay est utilisé
- `FLUTTERWAVE_SECRET_KEY=<test...>` si Flutterwave est utilisé

Important:

- pas de webhook live
- pas d’URL live
- pas de base prod

---

## 3. Audit statique non destructif

Depuis `backend/fastapi` ou la racine selon votre shell.

## 3.1 Compilation ciblée

```powershell
python -m py_compile `
  backend/fastapi/app/main.py `
  backend/fastapi/app/api/v1/api.py `
  backend/fastapi/app/api/v1/routers/admin.py `
  backend/fastapi/app/api/v1/routers/tasks.py `
  backend/fastapi/app/api/v1/routers/food.py `
  backend/fastapi/app/api/v1/routers/shop.py `
  backend/fastapi/app/api/v1/routers/vtc.py `
  backend/fastapi/app/services/food_service.py `
  backend/fastapi/app/services/shop_service.py `
  backend/fastapi/app/services/vtc_service.py `
  backend/fastapi/app/services/operations_resilience_service.py
```

Critère:

- aucune erreur

## 3.2 Audit backend readiness

```powershell
$env:PYTHONPATH="backend/fastapi"
python backend/fastapi/scripts/backend_readiness_audit.py
```

Critère:

- statut attendu: `ready_for_runtime_validation`
- si `blocked`, corriger avant toute suite

---

## 4. Vérification Alembic

## 4.1 Utiliser l’environnement de certification

Exemple PowerShell:

```powershell
$env:PYTHONPATH="backend/fastapi"
$env:DATABASE_URL="<database_staging_url>"
```

ou charger le fichier `.env.certification` via votre mécanisme standard.

## 4.2 Vérifier l’état courant

```powershell
cd backend/fastapi
alembic current
alembic heads
alembic history
```

Critères:

- une seule head
- historique cohérent
- base accessible

## 4.3 Appliquer les migrations sur staging

```powershell
alembic upgrade head
```

Critères:

- aucune erreur SQL
- aucune contrainte cassée
- aucune migration bloquée

## 4.4 Revalider l’état

```powershell
alembic current
```

Critère:

- la révision courante doit être la head

---

## 5. Démarrage backend

## 5.1 Démarrer l’API

Depuis `backend/fastapi`:

```powershell
$env:PYTHONPATH="."
uvicorn app.main:app --host 127.0.0.1 --port 6969
```

Critères:

- l’application démarre
- pas d’erreur d’import
- pas de hard-lock critique
- le scheduler démarre

## 5.2 Démarrer le worker Celery

Dans un second terminal:

```powershell
cd backend/fastapi
$env:PYTHONPATH="."
celery -A app.worker.celery_app.celery_app worker --loglevel=info
```

## 5.3 Démarrer Celery Beat si utilisé séparément

Dans un troisième terminal:

```powershell
cd backend/fastapi
$env:PYTHONPATH="."
celery -A app.worker.celery_app.celery_app beat --loglevel=info
```

Critères:

- worker OK
- beat OK
- aucune boucle d’échec immédiate

---

## 6. Health checks obligatoires

Exemples:

```powershell
Invoke-WebRequest http://127.0.0.1:6969/health
Invoke-WebRequest http://127.0.0.1:6969/health/ready
Invoke-WebRequest http://127.0.0.1:6969/health/db
Invoke-WebRequest http://127.0.0.1:6969/health/redis
Invoke-WebRequest http://127.0.0.1:6969/health/scheduler
Invoke-WebRequest http://127.0.0.1:6969/health/realtime
Invoke-WebRequest http://127.0.0.1:6969/health/ops
Invoke-WebRequest http://127.0.0.1:6969/health/backend-readiness
```

Critères:

- `/health` = ok
- `/health/ready` = ready
- `/health/db` = ok
- `/health/redis` = ok
- `/health/scheduler` = pas de job mort
- `/health/realtime` = pas de dégradation majeure
- `/health/ops` = pas de stale critique anormal
- `/health/backend-readiness` = `ready_for_runtime_validation` ou mieux

---

## 7. Scénarios backend critiques

Ces scénarios doivent être joués sur staging avec données de test.

## 7.1 Core task marketplace

- créer un client vérifié
- créer un tasker vérifié
- créer une tâche
- accepter la tâche
- compléter la tâche
- valider OTP
- vérifier:
  - escrow
  - release
  - split wallet
  - historique transaction

## 7.2 FOOD

- créer restaurant
- créer menu / items
- créer commande food
- financer
- confirmer restaurant
- passer en préparation
- créer livraison
- affecter livreur
- finaliser livraison
- vérifier:
  - meal hold
  - delivery escrow
  - payout restaurant
  - état commande

## 7.3 SHOP

- créer marchand
- créer catalogue / article
- créer commande shop
- financer
- confirmer marchand
- préparer
- créer livraison shop
- affecter tasker
- finaliser tâche
- vérifier:
  - merchandise hold
  - delivery escrow
  - payout marchand
  - stock

## 7.4 VTC

- créer client
- créer chauffeur + véhicule + profil validé
- passer chauffeur online
- créer course
- vérifier dispatch
- accepter/refuser
- faire le cycle:
  - en route
  - arrivé
  - démarrage
  - fin
- vérifier payout chauffeur

## 7.5 Compliance

- KYC incomplet → blocage attendu
- AML seuil > 500 EUR → review attendue
- dispute → freeze / résolution

---

## 8. Critères de sortie

Le backend est certifiable si:

- toutes les migrations passent
- l’API démarre
- le worker démarre
- les health checks sont verts
- les scénarios critiques passent
- aucun flux critique ne reste incohérent

---

## 9. Si échec

En cas d’échec, documenter:

- commande lancée
- environnement
- erreur exacte
- impact métier
- correctif requis
- priorité

Format conseillé:

- `critical`
- `high`
- `medium`
- `low`

---

## 10. Décision finale

On peut dire:

### “Backend production ready”

Seulement si:

- staging validé
- providers compatibles validés
- flux critiques validés
- aucun blocage `critical`

Sinon, la bonne formulation est:

### “Backend prêt pour corrections finales de certification”

---

## 11. Fichiers de référence

- `ZASKA_BACKEND_PRODUCTION_READY_CHECKLIST.md`
- `ZASKA_BACKEND_PROGRESS_APPENDIX.md`
- `ZASKA_MODULE_COMPLETENESS_MATRIX.md`
- `backend/fastapi/scripts/backend_readiness_audit.py`


---

## 12. Certification kit additions

- Environment template:
  - `backend/fastapi/.env.certification.example`
- Static audit:
  - `backend/fastapi/scripts/backend_readiness_audit.py`
- Runtime smoke checks:
  - `backend/fastapi/scripts/runtime_smoke_checks.py`

Suggested command:

```powershell
$env:PYTHONPATH="backend/fastapi"
python backend/fastapi/scripts/runtime_smoke_checks.py http://127.0.0.1:6969
```

Expected result:

- exit code `0`
- JSON status `passed`
- no failed health endpoints

## 13. Recommended execution path

For the safest backend certification flow, use two profiles:

- Local isolated certification:
  - `backend/fastapi/.env.certification.example`
- Shared staging certification:
  - `backend/fastapi/.env.certification.staging.example`

Unified command runner:

```powershell
$env:PYTHONPATH="backend/fastapi"
python backend/fastapi/scripts/validate_certification_env.py backend/fastapi/.env.certification
python backend/fastapi/scripts/run_backend_certification.py --env-file backend/fastapi/.env.certification --skip-runtime
python backend/fastapi/scripts/run_backend_certification.py --env-file backend/fastapi/.env.certification --base-url http://127.0.0.1:6969
```

Recommended order:

1. fill the local certification env
2. validate the env file
3. run static audit only
4. start API / worker / beat
5. run runtime smoke checks
6. repeat on shared staging
7. only then declare backend certified

## 14. Docker certification path

If you run ZASKA through Docker Compose, use the certification override file:

```powershell
docker compose -f docker-compose.yml -f docker-compose.certification.yml up -d postgres pgbouncer redis backend celery_worker celery_beat
```

Key points:

- backend runtime uses `pgbouncer:6432`
- Alembic uses `postgres:5432`
- Redis URLs include authentication on `redis:6379`
- `backend/fastapi/.env.certification` remains the local gitignored app env for certification
