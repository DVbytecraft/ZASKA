from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_DIR = Path(__file__).resolve().parent


def _load_env_file(env_file: str | None) -> Path | None:
    if not env_file:
        return None
    path = Path(env_file).resolve()
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()
    return path


def run_static_audit() -> dict[str, object]:
    from app.services.production_readiness_service import ProductionReadinessService

    return ProductionReadinessService().build_report()


def run_runtime_smoke(base_url: str, env_file: Path | None) -> subprocess.CompletedProcess[str]:
    command = [
        sys.executable,
        str(SCRIPTS_DIR / "runtime_smoke_checks.py"),
        base_url,
    ]
    env = os.environ.copy()
    if env_file is not None:
        env["ZASKA_CERTIFICATION_ENV_FILE"] = str(env_file)
    return subprocess.run(command, check=False, capture_output=True, text=True, env=env)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ZASKA backend certification checks.")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:6969",
        help="Base URL of the running backend for runtime smoke checks.",
    )
    parser.add_argument(
        "--skip-runtime",
        action="store_true",
        help="Run only the static readiness audit.",
    )
    parser.add_argument(
        "--env-file",
        help="Optional certification env file to load before running checks.",
    )
    args = parser.parse_args()

    loaded_env_file = _load_env_file(args.env_file)
    static_report = run_static_audit()
    output: dict[str, object] = {
        "env_file": str(loaded_env_file) if loaded_env_file else None,
        "static_audit": static_report,
        "runtime_smoke": None,
        "status": "passed",
    }

    if static_report.get("status") == "blocked":
        output["status"] = "failed"

    if not args.skip_runtime:
        runtime_result = run_runtime_smoke(args.base_url, loaded_env_file)
        runtime_payload: object
        try:
            runtime_payload = json.loads(runtime_result.stdout) if runtime_result.stdout.strip() else {}
        except json.JSONDecodeError:
            runtime_payload = {
                "stdout": runtime_result.stdout,
                "stderr": runtime_result.stderr,
            }
        output["runtime_smoke"] = {
            "returncode": runtime_result.returncode,
            "payload": runtime_payload,
            "stderr": runtime_result.stderr,
        }
        if runtime_result.returncode != 0:
            output["status"] = "failed"

    print(json.dumps(output, indent=2, ensure_ascii=False))

    if output["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
