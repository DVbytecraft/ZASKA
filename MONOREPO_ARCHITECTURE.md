# ZASKA Monorepo Architecture

## Applications

- `apps/web`: application React (Vite) qui réutilise l'UI existante.
- `apps/mobile`: application React Native (Expo) optimisée mobile.
- `backend/fastapi`: API commune (auth, tasks, payments).

## Shared Business Layer

`packages/shared-services` contient la logique métier partagée:

- `authService`: login et session.
- `taskService`: création de tâches.
- `paymentService`: récupération des moyens de paiement.
- `apiClient`: point unique des appels HTTP vers FastAPI.

## Separation of Concerns

- Les écrans web/mobile gèrent uniquement l'affichage + interactions utilisateur.
- La logique métier (requêtes API, payloads, mapping de réponse) est dans des services réutilisables.
- La base URL API est centralisée (`ZASKA_API_BASE_URL`, fallback `http://localhost:8000`).

## Consistency Across Platforms

- Web et mobile appellent les mêmes routes:
  - `POST /auth/login`
  - `POST /tasks`
  - `GET /payments/methods`
- Le flux auth/task/payment reste aligné entre plateformes.
