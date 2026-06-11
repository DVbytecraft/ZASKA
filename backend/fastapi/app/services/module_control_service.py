from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag
from app.models.location_config import Country
from app.models.module_control import ModuleActivationAudit, ModuleActivationSetting, PlatformModule
from app.services.country_rollout_service import CountryRolloutService
from app.services.geo_hierarchy_service import GeoHierarchyService


def _uuid() -> str:
    return str(uuid.uuid4())


class ModuleControlService:
    DEFAULT_MODULES = {
        "TASKS": {
            "label": "Tâches",
            "description": "Services à la demande et marketplace tasker.",
            "module_group": "marketplace",
            "default_enabled": True,
            "is_public": True,
            "requires_country_active": True,
        },
        "FOOD": {
            "label": "Food",
            "description": "Commande de repas, restaurants et livraison alimentaire.",
            "module_group": "marketplace",
            "default_enabled": False,
            "is_public": True,
            "requires_country_active": True,
        },
        "SHOP": {
            "label": "Boutique",
            "description": "Articles, cadeaux et marketplace produits.",
            "module_group": "marketplace",
            "default_enabled": False,
            "is_public": True,
            "requires_country_active": True,
        },
        "SUBSCRIPTIONS": {
            "label": "Abonnements",
            "description": "Abonnements Zaska Pro et abonnements de service.",
            "module_group": "billing",
            "default_enabled": False,
            "is_public": True,
            "requires_country_active": True,
        },
        "B2B": {
            "label": "B2B",
            "description": "Flux entreprises, contrats et opérations B2B.",
            "module_group": "enterprise",
            "default_enabled": False,
            "is_public": False,
            "requires_country_active": False,
        },
        "DIASPORA": {
            "label": "Diaspora",
            "description": "Commandes transfrontalières pour bénéficiaires tiers.",
            "module_group": "marketplace",
            "default_enabled": True,
            "is_public": True,
            "requires_country_active": True,
        },
        "TRANSPORT": {
            "label": "Transport",
            "description": "VTC et transport, préparé mais inactif par défaut.",
            "module_group": "transport",
            "default_enabled": False,
            "is_public": True,
            "requires_country_active": True,
        },
        "SOCIAL_PROTECTION": {
            "label": "Protection Sociale",
            "description": "Pension, santé, lissage et capital social tasker.",
            "module_group": "social",
            "default_enabled": True,
            "is_public": False,
            "requires_country_active": True,
        },
        "ACCOUNTING": {
            "label": "Comptabilité",
            "description": "Tableaux comptables, rapprochement et reporting financier.",
            "module_group": "admin",
            "default_enabled": True,
            "is_public": False,
            "requires_country_active": False,
        },
        "KYC_ADVANCED": {
            "label": "KYC Avancé",
            "description": "Contrôles KYC renforcés, casier et conformité avancée.",
            "module_group": "compliance",
            "default_enabled": True,
            "is_public": False,
            "requires_country_active": False,
        },
    }

    def __init__(self, db: Session):
        self.db = db

    def seed_catalog(self) -> None:
        existing = {
            row.code: row
            for row in self.db.execute(select(PlatformModule)).scalars().all()
        }
        changed = False
        for code, config in self.DEFAULT_MODULES.items():
            module = existing.get(code)
            if module is None:
                self.db.add(
                    PlatformModule(
                        code=code,
                        label=config["label"],
                        description=config["description"],
                        module_group=config["module_group"],
                        default_enabled=config["default_enabled"],
                        is_public=config["is_public"],
                        requires_country_active=config["requires_country_active"],
                    )
                )
                changed = True
                continue
            if (
                module.label != config["label"]
                or module.description != config["description"]
                or module.module_group != config["module_group"]
                or bool(module.default_enabled) != bool(config["default_enabled"])
                or bool(module.is_public) != bool(config["is_public"])
                or bool(module.requires_country_active) != bool(config["requires_country_active"])
            ):
                module.label = config["label"]
                module.description = config["description"]
                module.module_group = config["module_group"]
                module.default_enabled = config["default_enabled"]
                module.is_public = config["is_public"]
                module.requires_country_active = config["requires_country_active"]
                module.updated_at = datetime.now(timezone.utc)
                changed = True
        if changed:
            self.db.commit()

    def list_modules(self) -> list[dict]:
        self.seed_catalog()
        modules = self.db.execute(select(PlatformModule).order_by(PlatformModule.code.asc())).scalars().all()
        return [
            {
                "code": module.code,
                "label": module.label,
                "description": module.description,
                "module_group": module.module_group,
                "default_enabled": bool(module.default_enabled),
                "is_public": bool(module.is_public),
                "requires_country_active": bool(module.requires_country_active),
            }
            for module in modules
        ]

    def list_settings(
        self,
        *,
        module_code: str | None = None,
        scope_type: str | None = None,
        scope_value: str | None = None,
    ) -> list[dict]:
        self.seed_catalog()
        stmt = select(ModuleActivationSetting, PlatformModule).join(
            PlatformModule,
            PlatformModule.id == ModuleActivationSetting.module_id,
        )
        if module_code:
            stmt = stmt.where(PlatformModule.code == module_code.strip().upper())
        if scope_type:
            stmt = stmt.where(ModuleActivationSetting.scope_type == scope_type.strip().lower())
        if scope_value:
            stmt = stmt.where(ModuleActivationSetting.scope_value == scope_value.strip().upper())
        rows = self.db.execute(stmt.order_by(PlatformModule.code.asc(), ModuleActivationSetting.scope_type.asc(), ModuleActivationSetting.scope_value.asc())).all()
        return [
            {
                "module_code": module.code,
                "scope_type": setting.scope_type,
                "scope_value": setting.scope_value,
                "enabled": bool(setting.enabled),
                "config": self._decode_json(setting.config_json),
                "updated_at": setting.updated_at.isoformat() if setting.updated_at else None,
            }
            for setting, module in rows
        ]

    def resolve_modules_for_country(self, country_code: str, city_code: str | None = None) -> dict[str, dict]:
        self.seed_catalog()
        cc = country_code.strip().upper()
        country = CountryRolloutService(self.db).ensure_country(cc)
        modules = self.db.execute(select(PlatformModule)).scalars().all()
        chain = self._scope_chain(cc, city_code=city_code)

        return {
            module.code: self._resolve_module(module, country, chain)
            for module in modules
        }

    def is_module_enabled(self, country_code: str, module_code: str, city_code: str | None = None) -> bool:
        runtime = self.resolve_modules_for_country(country_code, city_code=city_code)
        entry = runtime.get(module_code.strip().upper())
        return bool(entry and entry["enabled"])

    def assert_module_enabled(self, country_code: str, module_code: str, city_code: str | None = None) -> None:
        if not self.is_module_enabled(country_code, module_code, city_code=city_code):
            module = module_code.strip().upper()
            raise ValueError(
                f"Le module {module} n'est pas encore accessible dans votre zone. "
                "Votre pays peut être configuré, mais ce service n'est pas encore lancé."
            )

    def upsert_setting(
        self,
        *,
        module_code: str,
        scope_type: str,
        scope_value: str,
        enabled: bool,
        changed_by_user_id: str | None = None,
        config: dict | None = None,
        reason: str | None = None,
    ) -> dict:
        self.seed_catalog()
        code = module_code.strip().upper()
        normalized_scope_type = scope_type.strip().lower()
        normalized_scope_value = scope_value.strip().upper()
        module = self.db.execute(select(PlatformModule).where(PlatformModule.code == code)).scalars().one_or_none()
        if module is None:
            raise ValueError(f"Module inconnu: {code}")
        if normalized_scope_type not in {"global", "continent", "country", "city"}:
            raise ValueError("scope_type doit être global, continent, country ou city.")
        if normalized_scope_type == "global":
            normalized_scope_value = "*"
        if normalized_scope_type == "country":
            CountryRolloutService(self.db).ensure_country(normalized_scope_value)

        config_json = json.dumps(config, sort_keys=True) if config is not None else None
        setting = self.db.execute(
            select(ModuleActivationSetting)
            .where(
                ModuleActivationSetting.module_id == module.id,
                ModuleActivationSetting.scope_type == normalized_scope_type,
                ModuleActivationSetting.scope_value == normalized_scope_value,
            )
            .with_for_update()
        ).scalars().one_or_none()

        previous_enabled = setting.enabled if setting is not None else None
        previous_config_json = setting.config_json if setting is not None else None

        if setting is None:
            setting = ModuleActivationSetting(
                module_id=module.id,
                scope_type=normalized_scope_type,
                scope_value=normalized_scope_value,
                enabled=enabled,
                config_json=config_json,
                created_by_user_id=changed_by_user_id,
                updated_by_user_id=changed_by_user_id,
            )
            self.db.add(setting)
        else:
            setting.enabled = enabled
            setting.config_json = config_json
            setting.updated_by_user_id = changed_by_user_id
            setting.updated_at = datetime.now(timezone.utc)

        self.db.add(
            ModuleActivationAudit(
                module_code=code,
                scope_type=normalized_scope_type,
                scope_value=normalized_scope_value,
                previous_enabled=previous_enabled,
                new_enabled=enabled,
                previous_config_json=previous_config_json,
                new_config_json=config_json,
                changed_by_user_id=changed_by_user_id,
                reason=reason,
            )
        )
        self.db.flush()
        self._sync_legacy_fields(
            module_code=code,
            scope_type=normalized_scope_type,
            scope_value=normalized_scope_value,
            enabled=enabled,
            config=config or {},
        )
        self.db.commit()
        self.db.refresh(setting)
        return {
            "module_code": code,
            "scope_type": normalized_scope_type,
            "scope_value": normalized_scope_value,
            "enabled": bool(setting.enabled),
            "config": self._decode_json(setting.config_json),
        }

    def _resolve_module(self, module: PlatformModule, country: Country, chain: list[tuple[str, str]]) -> dict:
        settings = self.db.execute(
            select(ModuleActivationSetting)
            .where(ModuleActivationSetting.module_id == module.id)
        ).scalars().all()
        setting_map = {
            (setting.scope_type, setting.scope_value): setting
            for setting in settings
        }

        enabled = bool(module.default_enabled)
        config: dict = {}
        source = "default"
        for scope_type, scope_value in chain:
            setting = setting_map.get((scope_type, scope_value))
            if setting is None:
                continue
            enabled = bool(setting.enabled)
            config = self._decode_json(setting.config_json)
            source = f"{scope_type}:{scope_value}"

        if module.code == "FOOD" and source == "default":
            enabled = bool(country.food_delivery_enabled)
            source = "legacy_country_flag"
        if module.requires_country_active and not bool(country.is_active):
            enabled = False
            source = "country_inactive"

        return {
            "enabled": enabled,
            "source": source,
            "config": config,
            "country_active": bool(country.is_active),
            "launch_status": country.launch_status,
        }

    def _scope_chain(self, country_code: str, city_code: str | None = None) -> list[tuple[str, str]]:
        cc = country_code.strip().upper()
        continent_code = GeoHierarchyService(self.db).get_continent_code(cc)
        chain: list[tuple[str, str]] = [("global", "*"), ("continent", continent_code), ("country", cc)]
        if city_code:
            chain.append(("city", city_code.strip().upper()))
        return chain

    def _sync_legacy_fields(
        self,
        *,
        module_code: str,
        scope_type: str,
        scope_value: str,
        enabled: bool,
        config: dict,
    ) -> None:
        if module_code != "FOOD" or scope_type != "country":
            return
        country = self.db.execute(
            select(Country).where((Country.iso_code == scope_value) | (Country.name == scope_value))
        ).scalars().one_or_none()
        if country is None:
            return
        country.food_delivery_enabled = enabled
        escrow_minutes = config.get("escrow_minutes")
        if isinstance(escrow_minutes, int) and escrow_minutes > 0:
            country.food_delivery_escrow_minutes = escrow_minutes

        flag = self.db.execute(
            select(FeatureFlag)
            .where(FeatureFlag.feature == "food_delivery_enabled", FeatureFlag.country_id == country.id)
            .with_for_update()
        ).scalars().one_or_none()
        if flag is None:
            self.db.add(
                FeatureFlag(
                    id=_uuid(),
                    feature="food_delivery_enabled",
                    country_id=country.id,
                    enabled=enabled,
                )
            )
        else:
            flag.enabled = enabled

    @staticmethod
    def _decode_json(raw: str | None) -> dict:
        if not raw:
            return {}
        try:
            data = json.loads(raw)
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}
