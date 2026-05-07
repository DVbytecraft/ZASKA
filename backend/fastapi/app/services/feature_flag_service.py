from sqlalchemy.orm import Session

from app.models.feature_flag import FeatureFlag


class FeatureFlagService:
    def __init__(self, db: Session):
        self.db = db

    def upsert_flag(self, feature: str, country_id: str, enabled: bool) -> FeatureFlag:
        flag = (
            self.db.query(FeatureFlag)
            .filter(FeatureFlag.feature == feature, FeatureFlag.country_id == country_id)
            .one_or_none()
        )
        if flag is None:
            flag = FeatureFlag(feature=feature, country_id=country_id, enabled=enabled)
            self.db.add(flag)
        else:
            flag.enabled = enabled
        self.db.commit()
        self.db.refresh(flag)
        return flag

    def list_flags(self, country_id: str | None = None) -> list[FeatureFlag]:
        query = self.db.query(FeatureFlag)
        if country_id:
            query = query.filter(FeatureFlag.country_id == country_id)
        return query.all()
