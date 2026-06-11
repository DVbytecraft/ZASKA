from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import settings


_REVISION_RE = re.compile(r'^revision\s*=\s*["\']([^"\']+)["\']', re.MULTILINE)
_DOWN_REVISION_RE = re.compile(r"^down_revision\s*=\s*(.+)$", re.MULTILINE)


@dataclass
class MigrationNode:
    revision: str
    down_revisions: list[str]
    file_name: str


class ProductionReadinessService:
    def build_report(self) -> dict[str, object]:
        config_report = self._build_config_report()
        migration_report = self._build_migration_report()
        import_report = self._build_import_report()

        failures = []
        for section_name, section in {
            "config": config_report,
            "migrations": migration_report,
            "imports": import_report,
        }.items():
            for check in section["checks"]:
                if not check["ok"]:
                    failures.append({"section": section_name, **check})

        status = "ready_for_runtime_validation" if not failures else "blocked"
        return {
            "status": status,
            "summary": {
                "failures": len(failures),
                "notes": [
                    "Cette vérification est non destructive.",
                    "Elle ne remplace pas la validation sur staging, les migrations réelles et les smoke tests runtime.",
                ],
            },
            "sections": {
                "config": config_report,
                "migrations": migration_report,
                "imports": import_report,
            },
            "failures": failures,
        }

    def _build_config_report(self) -> dict[str, object]:
        checks: list[dict[str, object]] = []
        env_norm = str(settings.env).strip().lower()

        checks.append(self._check("database_url_set", bool(settings.database_url.strip()), "DATABASE_URL est requis"))
        checks.append(self._check("jwt_secret_length", len(settings.jwt_secret.strip()) >= 32, "JWT_SECRET doit avoir au moins 32 caractères"))
        checks.append(self._check("api_prefix_set", bool(settings.api_prefix.strip()), "API prefix configuré"))
        checks.append(self._check("redis_url_set", bool(settings.redis_url.strip()), "Redis URL configuré"))
        checks.append(self._check("celery_broker_set", bool(settings.celery_broker_url.strip()), "Celery broker configuré"))
        checks.append(self._check("celery_backend_set", bool(settings.celery_result_backend.strip()), "Celery result backend configuré"))

        if env_norm == "production":
            checks.append(self._check("payment_mode_production", settings.payment_mode == "production", "ENV=production doit utiliser PAYMENT_MODE=production"))
            checks.append(self._check("zaska_wallet_user_id_set", bool(settings.zaska_wallet_user_id.strip()), "Wallet plateforme requis"))
            checks.append(self._check("otp_provider_enabled", bool(settings.otp_provider_enabled), "OTP provider doit être activé"))
            checks.append(self._check("kyc_provider_enabled", bool(settings.kyc_provider_enabled), "KYC provider doit être activé"))
            checks.append(
                self._check(
                    "at_least_one_live_payment_provider",
                    bool(
                        settings.stripe_secret_key.strip()
                        or settings.fedapay_api_key.strip()
                        or settings.flutterwave_secret_key.strip()
                        or settings.paystack_secret_key.strip()
                    ),
                    "Au moins un provider de paiement live est requis",
                )
            )
        else:
            checks.append(self._check("non_production_env_detected", True, f"ENV actuel = {env_norm or 'unknown'}"))

        return {"checks": checks}

    def _build_migration_report(self) -> dict[str, object]:
        versions_dir = Path(__file__).resolve().parents[2] / "alembic" / "versions"
        checks: list[dict[str, object]] = []
        nodes: list[MigrationNode] = []

        if not versions_dir.exists():
            return {
                "checks": [self._check("versions_dir_exists", False, f"Dossier migrations introuvable: {versions_dir}")],
                "details": {},
            }

        files = sorted(versions_dir.glob("*.py"))
        revisions_seen: set[str] = set()
        down_references: set[str] = set()
        duplicate_revisions: list[str] = []

        for file_path in files:
            raw = file_path.read_text(encoding="utf-8", errors="ignore")
            revision_match = _REVISION_RE.search(raw)
            down_revision_match = _DOWN_REVISION_RE.search(raw)
            revision = revision_match.group(1) if revision_match else ""
            down_revisions = self._parse_down_revisions(down_revision_match.group(1).strip() if down_revision_match else "None")
            if revision:
                if revision in revisions_seen:
                    duplicate_revisions.append(revision)
                revisions_seen.add(revision)
            down_references.update(down_revisions)
            nodes.append(MigrationNode(revision=revision, down_revisions=down_revisions, file_name=file_path.name))

        missing_down_refs = sorted(ref for ref in down_references if ref and ref not in revisions_seen)
        heads = sorted(node.revision for node in nodes if node.revision and node.revision not in down_references)
        roots = sorted(node.revision for node in nodes if node.revision and not node.down_revisions)

        checks.append(self._check("migration_files_present", len(files) > 0, f"{len(files)} fichier(s) de migration détecté(s)"))
        checks.append(self._check("no_duplicate_revisions", not duplicate_revisions, "Aucune révision Alembic dupliquée"))
        checks.append(self._check("no_missing_down_revisions", not missing_down_refs, "Toutes les down_revision pointent vers une migration existante"))
        checks.append(self._check("single_migration_head", len(heads) == 1, f"Head(s) détectée(s): {heads}"))
        checks.append(self._check("single_migration_root", len(roots) == 1, f"Root(s) détectée(s): {roots}"))

        return {
            "checks": checks,
            "details": {
                "migration_files": len(files),
                "heads": heads,
                "roots": roots,
                "missing_down_references": missing_down_refs,
                "duplicate_revisions": duplicate_revisions,
            },
        }

    def _build_import_report(self) -> dict[str, object]:
        modules = [
            "app.main",
            "app.api.v1.api",
            "app.services.vtc_service",
            "app.services.shop_service",
            "app.services.food_service",
            "app.services.operations_resilience_service",
            "app.worker.tasks",
            "app.worker.celery_app",
            "app.core.scheduler",
        ]
        checks = []
        for module_name in modules:
            try:
                importlib.import_module(module_name)
                checks.append(self._check(f"import:{module_name}", True, f"Import OK: {module_name}"))
            except Exception as exc:
                checks.append(self._check(f"import:{module_name}", False, f"Import KO: {module_name} -> {exc}"))
        return {"checks": checks}

    def _parse_down_revisions(self, raw_value: str) -> list[str]:
        if raw_value in {"None", "null"}:
            return []
        raw_value = raw_value.strip()
        if raw_value.startswith(("(", "[")):
            try:
                parsed = json.loads(raw_value.replace("'", '"'))
                if isinstance(parsed, list):
                    return [str(item) for item in parsed if item]
            except Exception:
                pass
            return re.findall(r"['\"]([^'\"]+)['\"]", raw_value)
        match = re.match(r"['\"]([^'\"]+)['\"]", raw_value)
        return [match.group(1)] if match else []

    @staticmethod
    def _check(name: str, ok: bool, message: str) -> dict[str, object]:
        return {"name": name, "ok": bool(ok), "message": message}
