# ZASKA — rapport d'exécution et de vérification

**Horizon :** validations effectuées le **2026-05-03** contre le dépôt courant après `docker compose up --build` sur l’environnement de l’agent. Les résultats dépendent de la machine et des ports définis dans `.env`.

## ✅ WORKING

- **`docker compose up --build`** : pile complète construite et démarrée ; services **postgres** (healthy), **redis** (healthy), **backend** (healthy), **frontend**, **celery_worker**, **celery_beat** (voir `docker compose ps`).
- **Ports hôtes évitablement conflictuels** : PostgreSQL **`5417→5432`**, Redis **`16379→6379`**, API **`6969`**, SPA **`3010`** (`docker-compose.yml` + variables `*_PUBLISH_PORT` dans `.env.example`).
- **Backend HTTP** : `GET http://127.0.0.1:6969/health` → **200** avec enveloppe `{"success":true,...}` observée lors des tests.
- **Frontend HTTP** : `GET http://127.0.0.1:3010/` → **200** (HTML Vite/React servi depuis le conteneur).
- **Base PostgreSQL 16 / PostGIS** : extension **`postgis`** présente ; tables **`users`, `tasks`, `countries`, `currencies`, `chat_messages`, etc.** listées ; **`countries`** = **6** lignées après seed (`docker compose exec postgres psql ...`).
- **Migrations Alembic** : `alembic upgrade head` exécuté dans le conteneur backend sans erreur ; révision **`20260502_0002 (head)`** rapportée par `alembic current`.
- **`Base.metadata.create_all`** : désactivé lorsque **`ENV=production`** (contrôle dans `app/main.py`).
- **Tests automatisés (conteneur backend, API joignable sur 127.0.0.1:6969)** : **`pytest` → 7 passed** après correctifs WS/fan-out, incluant :
  - auth : register → OTP (réponse ou Redis) → verify → login → refresh → logout (test existant étendu) ;
  - tâches : CRUD + **match** PostGIS ;
  - **WebSocket chat** : ticket `POST /api/auth/ws-ticket`, handshake `{type:"auth",ticket}`, réception temps réel du message ;
  - enveloppe d’erreur sur login invalide (**401**) ;
  - configuration OTP : **`Settings(env='production').expose_register_otp is False`**.
- **Celery worker** : journal **`celery@… ready`** et **`Connected to redis://redis:6379/1`** observés (`docker compose logs celery_worker`).
- **Sécurité — OTP** : en production configurée dans `Settings`, le drapeau **`expose_register_otp`** est forcé à **false** (vérifié par test unitaire léger et par exécution `Settings(env="production")` dans le conteneur).
- **Sécurité — WebSocket** : pas de JWT dans l’URL ; authentification par **ticket court** consommé côté serveur après acceptation de la socket.
- **Corrections livrées durant cette session** : suppression du **double `websocket.accept()`** ; fan-out chat **local fiable** (Redis `publish` conservé pour extension future).

## ❌ BROKEN

- **Aucun blocage fonctionnel critique** détecté sur la pile Docker **après** les correctifs ci-dessus sur l’agent (stack up, migrations, pytest verts).

## ⚠️ WARNINGS

- **PostgreSQL** : message serveur **`collation version mismatch`** sur la base `zaska` (à traiter avec `ALTER DATABASE … REFRESH COLLATION VERSION` ou alignement image/OS si problème réel en prod).
- **Chat temps réel multi-réplicas** : le diffuseur utilise **`publish` Redis + diffusion locale aux sockets du même processus**. Il n’y a **plus de listener Redis** actif dans l’API pour relayer entre **plusieurs pods Uvicorn** ; plusieurs instances nécessiteraient un pont Redis dédié (subscriber) ou sticky sessions / service messaging.
- **Limitation de débit** : middleware Redis fenêtré en place (**180 req / 60 s / IP typique**) ; une rafale de **185** requêtes `/health` depuis l’hôte n’a pas produit de **429** dans le comptage manuel utilisé (**180×200**, autres codes non ventilés) — garder une vérif métier (login throttling séparé côté auth existe).
- **Erreurs 404 hors routeur métier** : `GET /api/<inconnu>` renvoie `{"detail":"Not Found"}` (format Starlette standard), pas l’enveloppe `{ success, data, error }`.

## 🔐 SECURITY STATUS

| Sujet | État observé ou par code |
|--------|---------------------------|
| OTP absent en prod | ✅ `expose_register_otp=False` forcé si `ENV=production` (+ tests Settings) |
| JWT access / refresh | ✅ flux testés (login + refresh + logout avec blacklist refresh) |
| Expiration JWT | ⚙️ paramétrée dans `Settings` ; pas de mesure automatique durée réelle dans ce rapport |
| Rate limiting HTTP | ⚙️ Redis middleware actif ; test de charge fins non conclusifs côté agent |
| Fuite tracebacks API | ✅ gestionnaires globaux renvoient un message générique pour 500 (pas de test d’erreur forcée dans ce cycle) |
| WebSocket auth | ✅ ticket à usage court + première trame obligatoire |
| CORS / méthodes | ✅ `DELETE` autorisée pour compatibilité tâches (voir `main.py`) |

---

### Commandes de reproduction (référence)

```bash
docker compose up --build -d
docker compose exec -T -e TEST_API_URL=http://127.0.0.1:6969/api \
  -e TEST_WS_URL=ws://127.0.0.1:6969 \
  -e TEST_REDIS_URL=redis://redis:6379/0 \
  backend sh -c "cd /app/backend/fastapi && pytest -q"
```
