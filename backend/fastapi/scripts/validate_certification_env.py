from __future__ import annotations

import argparse
import json
from pathlib import Path


PLACEHOLDER_MARKERS = (
    "replace_me",
    "replace-",
    "change-me",
    "example",
    "your_",
    "todo",
)


REQUIRED_BASE_KEYS = (
    "ENV",
    "DATABASE_URL",
    "ALEMBIC_DATABASE_URL",
    "REDIS_URL",
    "JWT_SECRET",
    "OTP_SECRET",
    "PAYMENT_MODE",
    "OTP_PROVIDER",
    "OTP_PROVIDER_ENABLED",
    "KYC_PROVIDER_ENABLED",
)

AUTO_SEEDED_DOCKER_KEYS = (
    "ZASKA_WALLET_USER_ID",
    "PENSION_FUND_USER_ID",
    "HEALTH_FUND_USER_ID",
    "SMOOTHING_FUND_USER_ID",
)


def _parse_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        env[key.strip()] = value.strip()
    return env


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    return any(marker in normalized for marker in PLACEHOLDER_MARKERS)


def _validate(env: dict[str, str]) -> dict[str, object]:
    issues: list[dict[str, str]] = []
    runtime = env.get("CERTIFICATION_RUNTIME", "").strip().lower()
    docker_runtime = runtime == "docker-compose"

    for key in REQUIRED_BASE_KEYS:
        value = env.get(key, "").strip()
        if not value:
            issues.append({"key": key, "severity": "error", "reason": "missing"})
        elif _looks_like_placeholder(value):
            issues.append({"key": key, "severity": "error", "reason": "placeholder"})

    for key in AUTO_SEEDED_DOCKER_KEYS:
        value = env.get(key, "").strip()
        if docker_runtime and not value:
            issues.append({"key": key, "severity": "warning", "reason": "auto_seeded_at_runtime"})
            continue
        if value and _looks_like_placeholder(value):
            if docker_runtime:
                issues.append({"key": key, "severity": "warning", "reason": "auto_seeded_at_runtime"})
            else:
                issues.append({"key": key, "severity": "error", "reason": "placeholder"})
        elif not value and not docker_runtime:
            issues.append({"key": key, "severity": "error", "reason": "missing"})

    if env.get("ENV", "").strip().lower() == "staging":
        if env.get("OTP_PROVIDER", "").strip().lower() == "mock":
            issues.append({"key": "OTP_PROVIDER", "severity": "error", "reason": "mock_not_allowed_in_staging"})
        for key in ("BREVO_API_KEY", "EMAIL_FROM_ADDRESS", "PAYMENT_WEBHOOK_BASE_URL", "PAYMENT_REDIRECT_URL"):
            value = env.get(key, "").strip()
            if not value:
                issues.append({"key": key, "severity": "error", "reason": "missing_for_staging"})
            elif _looks_like_placeholder(value):
                issues.append({"key": key, "severity": "error", "reason": "placeholder_for_staging"})

    if env.get("PAYMENT_MODE", "").strip().lower() == "sandbox":
        if not env.get("STRIPE_SECRET_KEY", "").strip():
            issues.append({"key": "STRIPE_SECRET_KEY", "severity": "warning", "reason": "recommended_for_sandbox"})

    for key in ("REDIS_URL",):
        value = env.get(key, "").strip()
        if value.startswith("redis://") and "@redis:" in value and ":replace-redis-password@" not in value:
            continue
        if value.startswith("redis://") and "@localhost:" in value:
            issues.append({"key": key, "severity": "warning", "reason": "localhost_runtime_only"})
        if value.startswith("redis://") and "@redis:" not in value and "@localhost:" not in value:
            issues.append({"key": key, "severity": "warning", "reason": "review_redis_auth_or_host"})

    jwt_secret = env.get("JWT_SECRET", "").strip()
    if jwt_secret and len(jwt_secret) < 32:
        issues.append({"key": "JWT_SECRET", "severity": "error", "reason": "too_short"})

    otp_secret = env.get("OTP_SECRET", "").strip()
    if otp_secret and len(otp_secret) < 32:
        issues.append({"key": "OTP_SECRET", "severity": "error", "reason": "too_short"})

    status = "passed" if not any(issue["severity"] == "error" for issue in issues) else "failed"
    return {
        "status": status,
        "issues": issues,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a ZASKA backend certification env file.")
    parser.add_argument("env_file", help="Path to the certification env file to validate.")
    args = parser.parse_args()

    path = Path(args.env_file)
    if not path.exists():
        print(json.dumps({"status": "failed", "issues": [{"key": "env_file", "severity": "error", "reason": "not_found"}]}, indent=2))
        raise SystemExit(1)

    env = _parse_env_file(path)
    report = {
        "env_file": str(path),
        **_validate(env),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if report["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
