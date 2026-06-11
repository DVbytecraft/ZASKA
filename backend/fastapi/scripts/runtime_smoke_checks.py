from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass


DEFAULT_BASE_URL = "http://127.0.0.1:6969"


@dataclass(frozen=True)
class CheckDefinition:
    path: str
    expected_keywords: tuple[str, ...] = ()


CHECKS: tuple[CheckDefinition, ...] = (
    CheckDefinition("/health", ("ok",)),
    CheckDefinition("/health/ready", ("ready", "ok")),
    CheckDefinition("/health/db", ("ok",)),
    CheckDefinition("/health/redis", ("ok",)),
    CheckDefinition("/health/scheduler", ("ok", "healthy", "running")),
    CheckDefinition("/health/realtime", ("ok", "healthy", "connected")),
    CheckDefinition("/health/ops", ("ok", "healthy", "running")),
    CheckDefinition("/health/backend-readiness", ("ready_for_runtime_validation", "ready", "ok")),
)


def _normalize_text(payload: object) -> str:
    if isinstance(payload, dict):
        return json.dumps(payload, ensure_ascii=False).lower()
    return str(payload).lower()


def _extract_payload(response_body: str) -> object:
    try:
        return json.loads(response_body)
    except json.JSONDecodeError:
        return response_body


def _check_keywords(payload: object, expected_keywords: tuple[str, ...]) -> bool:
    if not expected_keywords:
        return True
    normalized = _normalize_text(payload)
    return any(keyword.lower() in normalized for keyword in expected_keywords)


def _fetch(base_url: str, check: CheckDefinition) -> dict[str, object]:
    url = f"{base_url.rstrip('/')}{check.path}"
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8", errors="replace")
            payload = _extract_payload(body)
            passed = response.status == 200 and _check_keywords(payload, check.expected_keywords)
            return {
                "path": check.path,
                "url": url,
                "status_code": response.status,
                "passed": passed,
                "payload": payload,
            }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        payload = _extract_payload(body)
        return {
            "path": check.path,
            "url": url,
            "status_code": exc.code,
            "passed": False,
            "payload": payload,
        }
    except Exception as exc:  # pragma: no cover - defensive smoke utility
        return {
            "path": check.path,
            "url": url,
            "status_code": None,
            "passed": False,
            "payload": {"error": str(exc)},
        }


def main() -> None:
    base_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("ZASKA_SMOKE_BASE_URL", DEFAULT_BASE_URL)
    results = [_fetch(base_url, check) for check in CHECKS]
    failed_checks = [result for result in results if not result["passed"]]
    output = {
        "base_url": base_url,
        "status": "passed" if not failed_checks else "failed",
        "checks": results,
        "failed_count": len(failed_checks),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    if failed_checks:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
