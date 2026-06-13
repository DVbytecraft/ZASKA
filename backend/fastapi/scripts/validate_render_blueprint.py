from __future__ import annotations

import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[3]
RENDER_BLUEPRINT = ROOT / "render.yaml"

BACKEND_REQUIRED_KEYS = {
    "DATABASE_URL",
    "PYTHONPATH",
    "ENV",
    "PAYMENT_MODE",
    "OTP_PROVIDER",
    "JWT_SECRET",
    "REDIS_URL",
    "BREVO_API_KEY",
    "EMAIL_FROM_ADDRESS",
    "APP_FRONTEND_URL",
    "CORS_ALLOWED_ORIGINS",
    "PAYMENT_WEBHOOK_BASE_URL",
    "PAYMENT_REDIRECT_URL",
}


def _env_map(service: dict[str, object]) -> dict[str, dict[str, object]]:
    env_vars = service.get("envVars") or []
    mapping: dict[str, dict[str, object]] = {}
    for item in env_vars:
        if isinstance(item, dict) and item.get("key"):
            mapping[str(item["key"])] = item
    return mapping


def main() -> None:
    blueprint = yaml.safe_load(RENDER_BLUEPRINT.read_text(encoding="utf-8"))
    services = blueprint.get("services") or []

    backend = next((svc for svc in services if svc.get("name") == "zaska-backend"), None)

    issues: list[dict[str, str]] = []

    if backend is None:
        issues.append({"severity": "error", "target": "zaska-backend", "reason": "missing_service"})

    if backend is not None:
        backend_env = _env_map(backend)
        for key in sorted(BACKEND_REQUIRED_KEYS):
            if key not in backend_env:
                issues.append({"severity": "error", "target": "zaska-backend", "reason": f"missing_env:{key}"})

    status = "passed" if not any(issue["severity"] == "error" for issue in issues) else "failed"
    print(
        json.dumps(
            {
                "status": status,
                "blueprint": str(RENDER_BLUEPRINT),
                "issues": issues,
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    if status != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
