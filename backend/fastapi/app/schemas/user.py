from pydantic import BaseModel, ConfigDict, Field


class UpdateProfilePayload(BaseModel):
    model_config = ConfigDict(strict=False)

    full_name: str | None = Field(default=None, max_length=128)
    first_name: str | None = Field(default=None, max_length=64)
    last_name: str | None = Field(default=None, max_length=64)
    avatar_url: str | None = Field(default=None, max_length=512)


class UserProfileResponse(BaseModel):
    id: str
    email: str
    role: str
    first_name: str | None
    last_name: str | None
    full_name: str | None
    phone: str | None
    avatar_url: str | None
    country_code: str | None
    is_verified: bool
