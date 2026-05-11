from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag


class FeatureFlagService:
    def __init__(self, db: Session):
        self.db = db

    def upsert_flag(self, feature: str, country_id: str, enabled: bool) -> FeatureFlag:
        # FOR UPDATE: prevents two concurrent admin upserts for the same (feature, country_id)
        # from both reading None and both trying to INSERT → IntegrityError or duplicate row.
        flag = self.db.execute(
            select(FeatureFlag)
            .where(FeatureFlag.feature == feature, FeatureFlag.country_id == country_id)
            .with_for_update()
        ).scalars().one_or_none()
        if flag is None:
            flag = FeatureFlag(feature=feature, country_id=country_id, enabled=enabled)
            self.db.add(flag)
            try:
                self.db.commit()
            except IntegrityError:
                self.db.rollback()
                flag = self.db.execute(
                    select(FeatureFlag)
                    .where(FeatureFlag.feature == feature, FeatureFlag.country_id == country_id)
                ).scalars().one()
                flag.enabled = enabled
                self.db.commit()
        else:
            flag.enabled = enabled
            self.db.commit()
        self.db.refresh(flag)
        return flag

    def list_flags(self, country_id: str | None = None) -> list[FeatureFlag]:
        stmt = select(FeatureFlag)
        if country_id:
            stmt = stmt.where(FeatureFlag.country_id == country_id)
        return self.db.execute(stmt).scalars().all()
