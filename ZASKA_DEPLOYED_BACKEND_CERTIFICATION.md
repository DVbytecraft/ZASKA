# ZASKA Deployed Backend Certification

Date: 2026-06-07

## Goal

Bridge the gap between:

- local Docker backend certification already passed
- real deployed backend certification still pending

## What is already certified

- local Docker environment
- static backend readiness audit
- migrations chain integrity
- import graph integrity
- runtime health endpoints
- Redis / PostgreSQL / scheduler / realtime / ops smoke checks

## What still must be verified on the deployed environment

- actual deployed env vars match backend expectations
- Redis URL is set and reachable
- worker uses the correct Celery app path
- backend and worker share the same JWT secret
- email provider values are present where worker tasks need them
- live `/health*` endpoints are green
- deployed logs show clean startup

## Repo-side deployment parity checks

Run:

```powershell
python backend/fastapi/scripts/validate_render_blueprint.py
```

Expected result:

- `status = passed`

## Live environment checks

Once the deployed backend URL is known, verify:

- `/health`
- `/health/ready`
- `/health/db`
- `/health/redis`
- `/health/scheduler`
- `/health/realtime`
- `/health/ops`
- `/health/backend-readiness`

## Final truth rule

The backend can be called **deployment-certified** only when:

1. local Docker certification is green
2. deployment blueprint parity is green
3. deployed runtime health is green
4. no startup/runtime errors remain in deployed logs
