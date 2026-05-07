import uuid

from sqlalchemy import Boolean, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class FeatureFlag(Base):
    __tablename__ = "feature_flags"
    __table_args__ = (UniqueConstraint("feature", "country_id", name="uq_feature_country"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    feature: Mapped[str] = mapped_column(String(100), index=True)
    country_id: Mapped[str] = mapped_column(String(36), ForeignKey("countries.id"), index=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
