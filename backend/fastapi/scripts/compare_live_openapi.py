from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare local ZASKA OpenAPI against a live deployment.")
    parser.add_argument("--base-url", required=True, help="Live backend base URL, e.g. https://zaska-backend.onrender.com")
    args = parser.parse_args()

    sys.path.insert(0, os.path.join(os.getcwd(), "backend", "fastapi"))
    from app.main import app

    local_paths = set(app.openapi()["paths"].keys())
    live = json.load(urllib.request.urlopen(f"{args.base_url.rstrip('/')}/openapi.json", timeout=60))
    live_paths = set(live["paths"].keys())

    missing_on_live = sorted(local_paths - live_paths)
    extra_on_live = sorted(live_paths - local_paths)

    critical_prefixes = (
        "/health/ops",
        "/health/backend-readiness",
        "/api/food",
        "/api/shop",
        "/api/vtc",
        "/api/subscriptions",
        "/api/referrals",
        "/api/aml",
        "/api/b2b",
        "/api/disputes",
        "/api/admin",
    )
    critical_missing = [path for path in missing_on_live if path.startswith(critical_prefixes)]

    report = {
        "base_url": args.base_url,
        "local_count": len(local_paths),
        "live_count": len(live_paths),
        "missing_on_live_count": len(missing_on_live),
        "extra_on_live_count": len(extra_on_live),
        "critical_missing_count": len(critical_missing),
        "critical_missing": critical_missing,
        "missing_on_live": missing_on_live,
        "extra_on_live": extra_on_live,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
