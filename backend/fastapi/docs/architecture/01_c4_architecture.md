# ZASKA — Architecture C4 Model
> Generated: 2026-05-31 | Source: Code inspection of 143 endpoints, 23 tables, 39 migrations

---

## Niveau 1 — Contexte système

```mermaid
C4Context
    title ZASKA — Contexte Système

    Person(client, "Client", "Créateur de tâches. Utilise l'app mobile/web.")
    Person(tasker, "Tasker", "Exécutant de tâches. Profil enrichi, badges, skills.")
    Person(admin, "Administrateur", "Modération, KYC, paiements, support.")

    System(zaska, "Plateforme ZASKA", "Marketplace de services de proximité. Gestion tâches, paiements escrow, trust & safety, messaging temps-réel.")

    System_Ext(stripe, "Stripe", "Paiements carte (Apple/Google Pay)")
    System_Ext(fedapay, "FedaPay", "Mobile Money Afrique de l'Ouest/Centrale")
    System_Ext(flutterwave, "Flutterwave", "Paiements Pan-Afrique")
    System_Ext(paystack, "Paystack", "Paiements Nigeria")
    System_Ext(cloudinary, "Cloudinary", "Stockage médias KYC + chat")
    System_Ext(rekognition, "AWS Rekognition", "Détection visage (photo vérification)")
    System_Ext(anthropic, "Anthropic Claude", "Modération IA (classification sévérité)")
    System_Ext(brevo, "Brevo / SendinBlue", "Emails transactionnels OTP/KYC")
    System_Ext(fcm, "Firebase FCM", "Notifications push mobile")
    System_Ext(turnstile, "Cloudflare Turnstile", "Protection anti-bot CAPTCHA")

    Rel(client, zaska, "Crée des tâches, effectue des paiements, chat")
    Rel(tasker, zaska, "Propose des services, reçoit des paiements escrow")
    Rel(admin, zaska, "Modère le contenu, approuve KYC, gère les incidents")

    Rel(zaska, stripe, "Crée payment intents, reçoit webhooks", "HTTPS/TLS")
    Rel(zaska, fedapay, "Mobile money West Africa", "HTTPS/TLS")
    Rel(zaska, flutterwave, "Pan-Africa payments", "HTTPS/TLS")
    Rel(zaska, paystack, "Nigeria payments", "HTTPS/TLS")
    Rel(zaska, cloudinary, "Upload/retrieve media", "HTTPS/TLS")
    Rel(zaska, rekognition, "DetectFaces API call", "AWS SDK / TLS")
    Rel(zaska, anthropic, "Messages API (severity)", "HTTPS/TLS")
    Rel(zaska, brevo, "Transactional email API", "HTTPS/TLS")
    Rel(zaska, fcm, "Push notifications HTTP v1", "HTTPS/TLS")
    Rel(zaska, turnstile, "Token verification", "HTTPS/TLS")
```

---

## Niveau 2 — Conteneurs

```mermaid
C4Container
    title ZASKA — Conteneurs

    Person(user, "Utilisateur", "Client / Tasker / Admin")

    Container(frontend, "Frontend React", "React 18 + Vite + TypeScript", "SPA mobile-first. Port 3010.")
    Container(api, "FastAPI Backend", "Python 3.13 + FastAPI 0.115", "143 endpoints REST + 3 WebSocket. Port 6969.")
    Container(scheduler, "Scheduler In-Process", "asyncio (APScheduler-like)", "8 jobs planifiés: escrows, outbox, payouts, reconciliation, trust recompute.")
    ContainerDb(postgres, "PostgreSQL 16", "Relationnel", "23 tables, 39 migrations. Données principales.")
    ContainerDb(redis, "Redis 7", "Cache + Pub/Sub", "Sessions JWT, rate limiting, tickets WS, pub/sub chat/calls, locks distribués.")
    Container(celery, "Celery Workers", "Python + Celery 5.4", "Workers asynchrones: webhooks, payouts, emails.")

    Rel(user, frontend, "Utilise", "HTTPS")
    Rel(frontend, api, "Appels REST + WebSocket", "HTTPS / WSS")
    Rel(api, postgres, "Lecture/écriture ORM", "SQLAlchemy + psycopg3")
    Rel(api, redis, "Cache, sessions, pub/sub", "redis-py sync + async")
    Rel(api, celery, "Enqueue tasks", "Redis broker")
    Rel(scheduler, postgres, "Lecture/écriture jobs", "SQLAlchemy")
    Rel(scheduler, redis, "Locks distribués", "SET NX + TTL")
    Rel(celery, postgres, "Process async jobs", "SQLAlchemy")
```

---

## Niveau 3 — Composants (FastAPI Backend)

```mermaid
C4Component
    title ZASKA FastAPI — Composants internes

    Component(api_layer, "API Layer", "19 routers FastAPI", "Endpoints REST + validation Pydantic. Auth via JWT Bearer.")
    Component(ws_layer, "WebSocket Layer", "3 managers", "Chat tasks, signaling WebRTC calls, notifications appels entrants.")
    Component(auth_svc, "AuthService", "JWT HS256 + bcrypt", "Register, login, OTP, refresh, blacklist, token versioning.")
    Component(payment_orch, "Payment Orchestrator", "4 providers + mock", "Stripe, FedaPay, Flutterwave, Paystack. Safety layer, idempotency, audit.")
    Component(wallet_svc, "WalletService", "Escrow engine", "Wallets multi-devises (XOF/XAF/GHS/NGN/KES/EUR/USD). Escrow 24h hold.")
    Component(trust_svc, "TrustService", "TrustScore + badges", "Score 0-100 (6 composantes). 8 badges. 20 skills. Seeding idempotent.")
    Component(moderation_svc, "ModerationService", "Claude Haiku + rule-based", "Détection injection. Retry AI 3x. Sort sévérité SQL.")
    Component(kyc_svc, "KYCService", "KYC + photo-vérif", "Soumission docs. Approbation admin. Rekognition detect_faces (face only — pas liveness).")
    Component(rate_limit, "Rate Limiter", "Lua Redis atomique", "Global 180 req/min. Par endpoint: IP + user_id dual-key.")
    Component(scheduler_comp, "Scheduler", "asyncio + Redis locks", "8 jobs. Watchdog heartbeat. Locks distribués multi-instance.")
    Component(outbox, "Outbox Pattern", "Transactional outbox", "Events table. Processed every 10s. Garantit delivery notifications/payouts.")

    Rel(api_layer, auth_svc, "Authenticate requests")
    Rel(api_layer, payment_orch, "Create/process payments")
    Rel(api_layer, wallet_svc, "Wallet ops + escrow")
    Rel(api_layer, trust_svc, "Trust score + reports")
    Rel(api_layer, moderation_svc, "Report + review cases")
    Rel(api_layer, kyc_svc, "KYC submission + photo")
    Rel(api_layer, rate_limit, "Per-endpoint rate check")
    Rel(api_layer, ws_layer, "Issue WS tickets")
    Rel(scheduler_comp, wallet_svc, "Auto-release escrows")
    Rel(scheduler_comp, moderation_svc, "Auto-escalate stale HIGH/CRITICAL")
    Rel(scheduler_comp, outbox, "Process outbox events")
```

---

## Flux de données critiques

### Flux paiement (escrow)

```
Client → POST /payments/create-intent
  → SafetyLayer (limits + fraud checks)
  → PaymentOrchestrator (provider selection par pays)
  → Provider externe (Stripe/FedaPay/etc.)
  ← Webhook provider → POST /payments/webhook/{provider}
    → Vérification signature HMAC
    → WalletService.fund_escrow()
    → OutboxEvent(type="escrow_funded")
    → Scheduler: release après 24h hold
```

### Flux modération

```
User → POST /trust/report
  → endpoint_rate_limit (5/300s IP + user_id)
  → ModerationService.report_content_sync() [rule-based, immediate]
  → BackgroundTask: ModerationService.enrich_with_ai()
    → _sanitize_for_prompt() [injection filtering]
    → _ai_severity() [Claude Haiku, retry 3x]
    → _ai_analysis() [Claude Haiku, retry 3x]
    → DB update case
  ← Admin: GET /moderation/cases [sorted CRITICAL→LOW]
```

### Flux WebSocket chat

```
User → POST /chat/{task_id}/ws-ticket
  → Redis SET ticket TTL 60s
  ← ticket (UUID)
User → WS /ws/tasks/{task_id}
  → auth message {type:"auth", ticket:"..."}
  → consume_ws_ticket() [one-time use, bound to task_id]
  → join room (max 50 connections)
  → messages via Redis pub/sub task-chat:{task_id}
  → fan-out cross-instance
```

---

## Inventaire des endpoints (143 total)

| Router | Endpoints | Auth | Rate Limited |
|--------|-----------|------|-------------|
| `/system` | 3 | No | Global only |
| `/auth` | 11 | Mixed | Yes (login/register/OTP) |
| `/users` | 4 | JWT | Global only |
| `/tasks` | 23 | JWT | Global only |
| `/payments` | 12 | Mixed | Partial |
| `/chat` | 4 | JWT | Global only |
| `/calls` | 5 | JWT | Global only |
| `/wallet` | 16 | JWT | Partial |
| `/feature-flags` | 2 | Mixed | Global only |
| `/kyc` | 6 | Mixed | Partial (photo: 3/hr) |
| `/admin` | 49 | Admin | Global only |
| `/trust` | 9 | Mixed | Yes (report: 5/5min) |
| `/moderation` | 6 | Admin | Global only |
| `/cards` | 3 | JWT | Global only |
| `/fx` | 2 | No | Global only |
| `/addresses` | 4 | JWT | Global only |
| `/statement` | 1 | JWT | Global only |
| `/notifications` | 4 | JWT | Global only |
| `/health` | 7 | No | None |

---

## Cartographie Redis (bases et usages)

| DB | Usage | Clés | TTL |
|----|-------|------|-----|
| 0 | Sessions + app | `blacklist:{token}`, `rl:*`, `ws_ticket:*`, `otp:*`, `fx:*`, `lock:*` | Varies |
| 1 | Celery broker | Celery task queue | Auto |
| 2 | Celery results | Celery result cache | Auto |

**Patterns de clés Redis (DB 0) :**
```
blacklist:{jwt_token}           → Token révoqué (logout/admin)
rl:http:{ip}:{window}           → Global rate limit
rl:ep:{prefix}:{ip}:{window}    → Endpoint rate limit (IP)
rl:ep:{prefix}:uid:{uid}:{win}  → Endpoint rate limit (user)
ws_ticket:{uuid}                → WebSocket ticket (TTL 60s)
otp:{phone_or_email}            → OTP code (TTL 5min)
fx:exposure:{XOF→USD}           → FX exposure tracker
lock:{job_name}                 → Distributed job lock (SET NX)
ver:{user_id}                   → Token version (password reset)
```

---

## Cartographie bases de données

### Tables principales (23+)

| Table | Rôle | Lignes estimées |
|-------|------|----------------|
| `users` | Comptes utilisateurs | Medium (10k-1M) |
| `tasks` | Tâches marketplace | High (100k+) |
| `wallets` | Wallets par devise | ~2× users |
| `transactions` | Ledger immuable | Very high |
| `escrows` | Fonds en séquestre | ~1× tasks |
| `kyc_submissions` | Dossiers KYC | ~users |
| `trust_scores` | Scores de confiance | ~users |
| `moderation_cases` | Cas de modération | Medium |
| `outbox_events` | Event sourcing | High (processed quickly) |
| `audit_logs` | Journal financier | Very high (append-only) |

### Index critiques
- `users.phone` UNIQUE INDEX
- `users.email` UNIQUE INDEX
- `tasks.status` INDEX
- `tasks.status, created_by` composite INDEX
- `transactions.wallet_id, created_at` composite INDEX
- `escrows.task_id` INDEX

---

## Cartographie services externes

| Service | Criticité | Fallback | Authentification |
|---------|-----------|----------|-----------------|
| PostgreSQL | **CRITIQUE** | Aucun | Connection string |
| Redis | **CRITIQUE** | Fail-open (rate limit) | URL (auth optionnel) |
| Stripe | Haute | FedaPay/Flutterwave | sk_live_ key |
| FedaPay | Haute | Flutterwave/mock | API key |
| Cloudinary | Haute | Upload échoue (503) | API key + secret |
| Brevo | Moyenne | Log only | API key |
| FCM | Moyenne | Log only | Service account JSON |
| AWS Rekognition | Basse | Mock auto-approve | Access key + secret |
| Anthropic | Basse | Rule-based fallback | API key |
| Turnstile | Basse | Bypass en dev | Secret key |
