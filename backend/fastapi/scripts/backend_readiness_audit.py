from __future__ import annotations

import json

from app.services.production_readiness_service import ProductionReadinessService


def main() -> None:
    report = ProductionReadinessService().build_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
