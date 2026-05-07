from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    feature: str = Field(min_length=2, max_length=100)
    country_id: str = Field(min_length=1, max_length=36)
    enabled: bool
