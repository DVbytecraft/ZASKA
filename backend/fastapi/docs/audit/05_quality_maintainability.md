# ZASKA — Audit Qualité & Maintenabilité (Étape 5)
> Generated: 2026-05-31

---

## Score qualité global : 72/100

| Dimension | Score | Commentaire |
|-----------|-------|-------------|
| Architecture modulaire | 85/100 | Layered arch, DI propre |
| Couverture de tests | 45/100 | 54 tests unitaires, 0 intégration |
| Dette technique | 65/100 | Duplication paiements, 2 modules payment/ |
| Cohérence du code | 80/100 | Style uniforme, Pydantic v2 |
| CI/CD | 30/100 | Pas de pipeline documenté |
| Complexité cyclomatique | 70/100 | Quelques fonctions complexes |
| Documentation | 60/100 | Docstrings partielles |

---

## Couverture de tests

### État actuel
- **54 tests unitaires** dans `tests/unit/test_step1_validation.py`
- **0 tests d'intégration** (endpoints non couverts)
- **0 tests de charge** (load testing)
- **0 tests de sécurité automatisés**
- **Coverage estimée : < 15%** du code de production

### Modules sans aucun test
- `app/services/payment_service.py` — CRITIQUE (argent réel)
- `app/services/wallet_service.py` — CRITIQUE (escrow, transferts)
- `app/services/auth_service.py` — ÉLEVÉ
- `app/api/v1/routers/payments.py` — CRITIQUE
- `app/api/v1/routers/tasks.py` — ÉLEVÉ
- `app/payment/safety_layer.py` — CRITIQUE
- `app/payment/limits.py` — CRITIQUE
- `app/services/trust_service.py` — MOYEN (partiel)

### Plan pour atteindre 80% coverage
1. Tests services critiques (wallet, payment) : 40 tests → +20%
2. Tests API endpoints (auth, tasks) : 30 tests → +15%
3. Tests sécurité (rate limit bypass, RBAC) : 20 tests → +10%
4. Total : ~144 tests → ~80% coverage estimée

---

## Dette technique

### DT-01 — Double module `payment/` [HAUTE]
```
app/services/payment/     # Provider implementations
app/payment/              # Safety layer, orchestrator, limits
```
Duplication de logique. Même provider Stripe existe en `services/payment/stripe_provider.py` ET `payment/providers/stripe_provider.py`.
**Fix :** Fusionner en `app/payment/` unique. Supprimer `app/services/payment/`.

### DT-02 — Routes admin très longues [MOYEN]
`app/api/v1/routers/admin.py` : 49 endpoints dans un seul fichier.
Difficile à maintenir et tester.
**Fix :** Splitter en `admin/users.py`, `admin/payments.py`, `admin/moderation.py`, etc.

### DT-03 — Schémas Pydantic incomplets [MOYEN]
Certains endpoints retournent des dicts Python plutôt que des modèles Pydantic.
`_serialize()` manuel dans moderation_service, trust, kyc...
**Fix :** Migrer vers des modèles Pydantic avec `response_model=` sur chaque endpoint.

### DT-04 — Configuration monolithique [MOYEN]
`app/core/config.py` : 80+ settings dans une seule classe.
Difficile de séparer les concerns (payment, redis, ai, etc.)
**Fix :** Sous-classes `RedisSettings`, `PaymentSettings`, `AISettings` via `model_config`.

### DT-05 — Celery sous-utilisé [FAIBLE]
`app/worker/` et `app/workers/` existent mais sont peu utilisés.
Webhook processing se fait en sync dans les routers.
**Fix :** Migrer webhook processing vers Celery workers.

---

## Complexité cyclomatique (estimée par inspection)

| Fonction | Complexité estimée | Risque |
|---------|-------------------|--------|
| `config.py Settings.__init__` | ~25 | ÉLEVÉ — validation imbriquée |
| `admin.py` routes individuelles | ~8-12 | MOYEN |
| `payment_service.py` orchestration | ~15+ | ÉLEVÉ |
| `trust_service.py compute_for_user` | ~10 | MOYEN |
| `moderation_service.py enrich_with_ai` | ~8 | FAIBLE |
| `auth_service.py register` | ~12 | MOYEN |

**Recommandation :** Tout ce qui dépasse CC=10 doit être refactoré.

---

## Cohérence du code

### Points positifs
- Style uniforme (pas de mélange snake_case/camelCase dans Python)
- Pydantic v2 utilisé partout
- SQLAlchemy 2.0 (select() moderne, pas de query())
- Loguru pour logging cohérent
- `success_response()` / `error_response()` standards

### Incohérences
- `_serialize()` vs Pydantic `response_model` (mixte)
- `from __future__ import annotations` présent dans certains fichiers seulement
- Certains services utilisent `db.query(Model)` (SQLAlchemy 1.x style) au lieu de `select(Model)`

---

## CI/CD

### État actuel
- Aucun pipeline CI/CD documenté trouvé dans le repo
- Pas de `.github/workflows/` ou `Dockerfile` identifié dans les docs
- Tests exécutés manuellement via `python -m pytest`

### Plan CI/CD recommandé
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres: {image: postgres:16}
      redis: {image: redis:7}
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  security:
    runs-on: ubuntu-latest
    steps:
      - run: pip install bandit safety
      - run: bandit -r app/ -ll
      - run: safety check -r requirements.txt

  lint:
    runs-on: ubuntu-latest
    steps:
      - run: pip install ruff mypy
      - run: ruff check app/
      - run: mypy app/ --ignore-missing-imports
```

---

## Recommandations prioritaires

1. **Coverage 80%** : Tests wallet_service, payment_service, auth_service — bloquant pour production fintech
2. **DT-01** : Fusionner les deux modules payment (2 jours de refactoring)
3. **CI/CD** : Pipeline GitHub Actions basique (2h de setup)
4. **response_model** : Pydantic sur tous les endpoints (améliore docs OpenAPI + validation sortie)
5. **Monitoring** : Sentry DSN configuré ? Prometheus métriques exposées `/health/metrics`
