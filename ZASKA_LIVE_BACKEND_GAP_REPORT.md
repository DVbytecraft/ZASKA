# ZASKA Live Backend Gap Report

Date: 2026-06-07
Live URL checked: `https://zaska-backend.onrender.com`

## What passed live

- `GET /health` → `200`
- `GET /health/ready` → `200`
- `GET /health/db` → `200`
- `GET /health/redis` → `200`
- `GET /health/scheduler` → `200`
- `GET /health/realtime` → `200`
- `GET /openapi.json` → `200`

## What failed live

- `GET /health/ops` → `404`
- `GET /health/backend-readiness` → `404`

## Contract comparison

- Local certified backend paths: `305`
- Live deployed backend paths: `157`
- Missing on live vs local: `148`
- Extra on live vs local: `0`

## Conclusion

The deployed backend is **not yet at parity** with the certified local backend.

This means:

- the local/backend codebase is far ahead of the currently deployed service
- the live deployment is running an older backend surface
- frontend work should not start yet if the goal is to target the new backend contract safely

## Highest-priority missing live surfaces

- `/health/ops`
- `/health/backend-readiness`
- `/api/food/*`
- `/api/shop/*`
- `/api/vtc/*`
- `/api/subscriptions/*`
- `/api/referrals/*`
- `/api/aml/*`
- `/api/b2b/*`
- `/api/disputes/*`
- large parts of `/api/admin/*`

## Truthful status

- Local Docker backend: certified
- Repository deployment blueprint: aligned
- Live deployed backend: **not yet fully updated to the certified backend**

## Next required action

Deploy the current backend revision, then rerun:

```powershell
python backend/fastapi/scripts/compare_live_openapi.py --base-url https://zaska-backend.onrender.com
```
