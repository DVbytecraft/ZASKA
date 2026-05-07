"""
FeatureFlagEngine — merge flags statiques (registry) + overrides DB.

Stratégie de résolution (priorité décroissante) :
  1. Cache Redis (TTL 60 s)
  2. Overrides DB  (table feature_flags, Country.name == country_code)
  3. Defaults statiques (CountryConfig.feature_flags_defaults)

Les overrides DB permettent aux admins de modifier un flag sans redéploiement.
La table Country est recherchée par `name == country_code` (convention de seed).
"""

from __future__ import annotations

import json

from redis import Redis
from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag
from app.models.location_config import Country

from .definitions import get_config

FLAG_CACHE_TTL = 60  # secondes — conforme au cahier des charges


class FeatureFlagEngine:

    def __init__(self, redis_client: Redis, db: Session) -> None:
        self._redis = redis_client
        self._db = db

    # ── Lecture ───────────────────────────────────────────────────────────

    def get_flags(self, country_code: str) -> dict[str, bool]:
        """
        Retourne le dictionnaire complet des flags pour un pays.
        Toujours garanti de retourner au moins les defaults statiques.
        """
        cc = country_code.upper()
        cache_key = f"features:{cc}"

        cached = self._redis.get(cache_key)
        if cached:
            return json.loads(cached)

        flags = self._build_flags(cc)
        self._redis.setex(cache_key, FLAG_CACHE_TTL, json.dumps(flags))
        return flags

    def get_flag(self, country_code: str, feature: str) -> bool:
        """Raccourci pour lire un flag précis."""
        return self.get_flags(country_code).get(feature, False)

    # ── Écriture (admin) ─────────────────────────────────────────────────

    def set_flag(self, country_code: str, feature: str, enabled: bool) -> None:
        """
        Override DB d'un flag pour un pays.
        Invalide le cache Redis immédiatement.

        Raises ValueError si le pays n'existe pas encore en base.
        """
        cc = country_code.upper()
        country_row = self._db.query(Country).filter(Country.name == cc).one_or_none()
        if country_row is None:
            raise ValueError(
                f"Pays '{cc}' introuvable en base. "
                "Seed la table countries avec Country.name == country_code."
            )

        flag = (
            self._db.query(FeatureFlag)
            .filter(FeatureFlag.feature == feature, FeatureFlag.country_id == country_row.id)
            .one_or_none()
        )
        if flag is None:
            flag = FeatureFlag(feature=feature, country_id=country_row.id, enabled=enabled)
            self._db.add(flag)
        else:
            flag.enabled = enabled
        self._db.commit()
        self._invalidate_cache(cc)

    def bulk_set_flags(self, country_code: str, updates: dict[str, bool]) -> None:
        """Override de plusieurs flags en une transaction."""
        cc = country_code.upper()
        country_row = self._db.query(Country).filter(Country.name == cc).one_or_none()
        if country_row is None:
            raise ValueError(f"Pays '{cc}' introuvable en base.")

        for feature, enabled in updates.items():
            flag = (
                self._db.query(FeatureFlag)
                .filter(FeatureFlag.feature == feature, FeatureFlag.country_id == country_row.id)
                .one_or_none()
            )
            if flag is None:
                self._db.add(FeatureFlag(feature=feature, country_id=country_row.id, enabled=enabled))
            else:
                flag.enabled = enabled

        self._db.commit()
        self._invalidate_cache(cc)

    # ── Internals ────────────────────────────────────────────────────────

    def _build_flags(self, cc: str) -> dict[str, bool]:
        """Merge statique + DB (sans cache)."""
        config = get_config(cc)
        flags: dict[str, bool] = dict(config.feature_flags_defaults)

        country_row = self._db.query(Country).filter(Country.name == cc).one_or_none()
        if country_row is not None:
            db_flags = (
                self._db.query(FeatureFlag)
                .filter(FeatureFlag.country_id == country_row.id)
                .all()
            )
            for f in db_flags:
                flags[f.feature] = f.enabled

        return flags

    def _invalidate_cache(self, cc: str) -> None:
        self._redis.delete(f"features:{cc}")
