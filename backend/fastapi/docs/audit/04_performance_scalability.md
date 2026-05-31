# ZASKA — Audit Performance & Scalabilité (Étape 4)
> Generated: 2026-05-31 | Source: Code analysis (pas de live load testing — infrastructure indisponible)

---

## Limites réelles estimées (sans load testing)

| Scénario | Limite estimée | Goulot d'étranglement |
|----------|---------------|----------------------|
| 100 utilisateurs concurrents | OK | Aucun |
| 1 000 utilisateurs concurrents | Tendu | DB pool (30 conns) + Redis 200 |
| 10 000 utilisateurs concurrents | Insuffisant | DB pool saturation, Redis pub/sub lag |
| Webhooks burst (100/s) | Risqué | Outbox processing (10s interval) |

---

## PostgreSQL

### Points positifs
- Pool configuré : `pool_size=10, max_overflow=20` → 30 connexions max
- `pool_recycle=1800` : évite les connexions stale
- Indexes critiques présents : `users.phone`, `users.email`, `tasks.status`, `transactions.(wallet_id, created_at)`
- Outbox pattern : les notifications ne bloquent pas le thread principal

### Problèmes identifiés

**P-01 — N+1 Queries dans la liste des tâches [MOYEN]**
- `GET /tasks` : probable N+1 sur chargement du `assigned_to` user pour chaque tâche
- Fix : `joinedload(Task.tasker)` ou `selectinload()`
- Impact : 100 tâches = 101 queries au lieu de 2

**P-02 — Absence d'index sur `escrows.status` [MOYEN]**
- `release_held_escrows` (toutes les 30s) scanne toute la table
- À mesure que les escrows s'accumulent → full table scan toutes les 30s
- Fix : `CREATE INDEX ix_escrow_status ON escrows(status)` dans migration

**P-03 — Pool insuffisant pour 1000+ users [ÉLEVÉ]**
- 30 connexions max pour 1000 requêtes concurrentes
- Fix : PgBouncer en transaction mode (déjà documenté)
- Ou : `pool_size=20, max_overflow=40` pour scaling vertical simple

**P-04 — `audit_logs` croissance illimitée [MOYEN]**
- Table append-only sans partitioning ni archivage
- À 1M transactions/jour → table de 365M lignes en 1 an
- Fix : Partitioning par mois (`PARTITION BY RANGE (created_at)`)

**P-05 — `outbox_events` traité toutes les 10s [FAIBLE]**
- Délai max 10s pour notifications post-paiement
- Acceptable mais peut être réduit à 2s si nécessaire

### Recommandations indexes supplémentaires

```sql
-- Manquants identifiés
CREATE INDEX ix_escrow_status ON escrows(status) WHERE status IN ('hold', 'funded');
CREATE INDEX ix_outbox_processed ON outbox_events(processed_at) WHERE processed_at IS NULL;
CREATE INDEX ix_moderation_status_sev ON moderation_cases(status, severity);
CREATE INDEX ix_notification_user_read ON notifications(user_id, is_read) WHERE is_read = false;
CREATE INDEX ix_task_scheduled ON tasks(scheduled_at) WHERE scheduled_at IS NOT NULL;
```

---

## Redis

### Points positifs
- `MAX_ASYNC_CONNECTIONS=200` : pool async correctement dimensionné
- Eviction policy documentée (LRU recommandé pour sessions)
- Pub/sub pour chat et appels : scalable cross-instance
- Atomic Lua scripts (rate limiting) : pas de TOCTOU

### Problèmes identifiés

**P-06 — Pub/Sub sans backpressure [MOYEN]**
- 10 000 connexions WS simultanées = 10 000 messages Redis pub/sub par message
- Pas de batching ou de throttling
- Fix : Batching côté WS manager (100ms window)

**P-07 — SCAN OTP cleanup pas optimisé [FAIBLE]**
- `SCAN` toutes les 5 minutes est O(N) sur toutes les clés Redis
- Si beaucoup de clés → ralentissement
- Fix : Utiliser TTL natif Redis (les clés OTP ont déjà TTL 5min)
- Supprimer le job `otp_cleanup` — Redis expire les clés automatiquement

**P-08 — Sentinel non configuré = SPOF Redis [ÉLEVÉ]**
- Sans Sentinel, Redis est un SPOF
- Downtime Redis = impossibilité de login (blacklist), rate limiting down, WS tickets invalides
- Fix : Déployer Sentinel (script créé C-01)

---

## FastAPI / Uvicorn

### Points positifs
- `uvloop` configuré (2-4x plus rapide que asyncio par défaut)
- Middleware stack bien ordonné
- `asyncio.to_thread()` pour appels bloquants (Rekognition)
- BackgroundTasks pour enrichissement IA

### Problèmes identifiés

**P-09 — BackgroundTasks Uvicorn non persistants [MOYEN]**
- `BackgroundTasks` FastAPI s'exécute dans le même processus Uvicorn
- Si Uvicorn redémarre pendant `enrich_with_ai()` → tâche perdue
- Fix : Pour les tâches critiques, utiliser Celery (déjà présent mais sous-utilisé)
- `enrich_with_ai` est non-critique (sévérité rule-based comme fallback) → acceptable

**P-10 — Pas de timeout sur les appels externes [ÉLEVÉ]**
- Appels Anthropic, Rekognition, Cloudinary sans timeout explicite
- Un provider lent bloque le thread pendant N secondes
- Fix : `timeout=30` sur tous les appels HTTP externes

**P-11 — Workers Celery non utilisés pour paiements [MOYEN]**
- Webhook processing se fait en sync dans le router (avec DB in-request)
- Pour 100 webhooks/s → goulot d'étranglement sur pool DB
- Fix : Queue webhooks vers Celery, libérer le thread HTTP immédiatement

---

## Analyse des endpoints critiques

| Endpoint | DB Queries | Externe | Latence estimée | Risque |
|----------|-----------|---------|-----------------|--------|
| `POST /auth/login` | 2 (user + token) | Redis | 50ms | Faible |
| `POST /payments/create-intent` | 5+ | Stripe/FedaPay | 500-2000ms | Élevé |
| `GET /tasks` | 2-100 (N+1 possible) | Aucun | 20-500ms | Moyen |
| `POST /kyc/photo-verification` | 3 | AWS Rekognition | 1000-5000ms | Élevé |
| `POST /trust/report` | 2 | Redis | 50ms | Faible |
| `WS /ws/tasks/{id}` | 0 (pub/sub) | Redis | <5ms/msg | Très faible |

---

## Plan load testing (à exécuter sur infra réelle)

```bash
# Outil recommandé : locust ou k6

# Scénario 1 : 100 users authentifiés browsing tasks
locust -f tests/load/scenario_browse.py --users=100 --spawn-rate=10

# Scénario 2 : 50 users créant des tâches simultanément  
locust -f tests/load/scenario_create_tasks.py --users=50

# Scénario 3 : Burst webhooks (simuler 50 paiements simultanés)
locust -f tests/load/scenario_webhooks.py --users=50 --run-time=60s

# Métriques à surveiller :
# - p95 latency < 500ms pour endpoints non-externes
# - Error rate < 0.1%
# - DB pool waitqueue = 0
# - Redis ops < 10k/s
```

---

## Limites documentées

| Métrique | Valeur actuelle | Limite recommandée |
|----------|-----------------|-------------------|
| DB connections max | 30 | 100 (avec PgBouncer) |
| Redis async pool | 200 | OK jusqu'à 5k users |
| WS connections/instance | 10 000 (calls) | OK |
| Rate limit global | 180 req/min/IP | OK |
| Backoff AI retries | 2s + 5s | OK (background) |
| Escrow check interval | 30s | OK |
| Outbox processing | 10s | OK (réduire si besoin) |
