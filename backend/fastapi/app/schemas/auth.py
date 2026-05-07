import re

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LoginPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)
    password: str = Field(min_length=6, max_length=128)

    @field_validator("phone")
    @classmethod
    def phone_strip(cls, v: str) -> str:
        return v.strip()


class RegisterPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)
    firstName: str = Field(min_length=1, max_length=64)
    lastName: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    email: str | None = Field(default=None, min_length=5, max_length=255)
    role: str = Field(default="client", pattern="^(client|tasker)$")
    country: str | None = Field(default=None, max_length=2)

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip().lower()

    @field_validator("country")
    @classmethod
    def country_uppercase(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("country must be a 2-letter ISO code (e.g. SN, TG, FR)")
        return v

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class SetPasswordPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    email: str = Field(min_length=5, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @field_validator("email")
    @classmethod
    def email_lowercase(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class VerifyOtpPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)
    code: str = Field(min_length=4, max_length=10)

    @field_validator("phone")
    @classmethod
    def phone_strip(cls, v: str) -> str:
        return v.strip()


class RefreshPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    refresh_token: str


class TokenResponse(BaseModel):
    accessToken: str
    refreshToken: str
    userId: str


class ForgotPasswordPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)

    @field_validator("phone")
    @classmethod
    def phone_strip(cls, v: str) -> str:
        return v.strip()


class ResetPasswordPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=8, max_length=128)

    @field_validator("phone")
    @classmethod
    def phone_strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one digit")
        return v


class ResendOtpPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    phone: str = Field(min_length=7, max_length=20)

    @field_validator("phone")
    @classmethod
    def phone_strip(cls, v: str) -> str:
        return v.strip()


class LogoutPayload(BaseModel):
    model_config = ConfigDict(strict=True)

    refresh_token: str
