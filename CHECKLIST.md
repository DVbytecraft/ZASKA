# CHECKLIST ZASKA — uniquement les points **vérifiés** lors du dernier run

Légende : **[x]** = vérifié sur cet environnement · **[ ]** = non vérifié / partiel dans ce rapport

## Infra Docker

- [x] `docker compose up --build` démarre **postgres**, **redis**, **backend**, **frontend**, **celery_worker**, **celery_beat`
- [x] Ports externes configurables (**Postgres**, **Redis**, **backend**, **frontend**) via `.env` / `.env.example`
- [x] Backend répond **`http://localhost:6969/health`** (200)
- [x] Frontend répond **`http://localhost:3010/`** (200)

## Base de données

- [x] PostgreSQL joignable, volume persistant défini dans Compose
- [x] PostGIS (**extension présente**)
- [x] `alembic upgrade head` OK en conteneur ; révision **head** affichée
- [x] Seed pays : **`SELECT COUNT(*) FROM countries` → 6**
- [x] `ENV=production` → **pas de `create_all`** au startup (contrôle lecture code + logique prod)

## Backend API

- [x] Enveloppe commune sur routes métier testées (**auth**, **tasks**, **erreur login**)
- [x] Auth : register, verify OTP (dev + lecture Redis fallback tests), login, refresh, logout
- [x] Tâches : create, list, get, patch, delete, match (PostGIS)
- [x] Chat WebSocket : ticket REST + handshake JSON + réception du message envoyé
- [x] Middleware rate limit Redis présent (**non prouvé 429 systématique** sur burst `/health`)

## Frontend (smoke HTTP)

- [x] Page d’accueil Vite servie depuis le conteneur (**pas** de clic bouton automatisé dans ce run)

## Qualité automatique

- [x] Suite **`pytest`** dans le backend conteneurisé : **7 tests passés** (auth, tasks, e2e WS, enveloppe erreur login, réglages OTP prod/dev)

## Non vérifié dans ce rapport (à traiter séparément)

- [ ] Parcours UI manuel bouton-par-bouton (login SPA, création tâche, chat navigateur)
- [ ] Débit 429 garanti sous charge contrôlée (artillerie dédiée)
- [ ] Plusieurs replicas backend + propagation chat ** entre ** instances uniquement via Redis**
