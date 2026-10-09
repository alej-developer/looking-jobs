"""Request and response models. Field limits keep stored text bounded."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from database import VALID_STATUSES

_TEXT = 4000
_SHORT = 300


class LoginRequest(BaseModel):
    token: str = Field(min_length=1, max_length=512)


class BridgeItem(BaseModel):
    skill: str = Field(min_length=1, max_length=200)
    evidence: str = Field(min_length=1, max_length=_TEXT)


class ProfileUpdate(BaseModel):
    full_name: str = Field(default="", max_length=_SHORT)
    email: str = Field(default="", max_length=_SHORT)
    phone: str = Field(default="", max_length=40)
    origin_sector: str = Field(default="", max_length=_SHORT)
    origin_role: str = Field(default="", max_length=_SHORT)
    origin_years: int | None = Field(default=None, ge=0, le=60)
    origin_highlights: str = Field(default="", max_length=_TEXT)
    target_roles: str = Field(default="", max_length=_TEXT)
    target_sectors: str = Field(default="", max_length=_TEXT)
    seniority: str = Field(default="", max_length=80)
    constraints_text: str = Field(default="", max_length=_TEXT)
    bridge: list[BridgeItem] = Field(default_factory=list, max_length=12)
    anchors: dict[str, str] = Field(default_factory=dict)
    proof: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("anchors")
    @classmethod
    def _known_anchors(cls, value: dict[str, str]) -> dict[str, str]:
        allowed = {"why_change", "why_company", "what_you_bring"}
        unknown = set(value) - allowed
        if unknown:
            raise ValueError("unknown anchor keys")
        cleaned: dict[str, str] = {}
        for key, text in value.items():
            if len(text) > _TEXT:
                raise ValueError("anchor text is too long")
            cleaned[key] = text
        return cleaned

    @field_validator("proof")
    @classmethod
    def _proof_limits(cls, value: list[str]) -> list[str]:
        for item in value:
            if len(item) > _TEXT:
                raise ValueError("proof item is too long")
        return value

    @field_validator("email")
    @classmethod
    def _email_shape(cls, value: str) -> str:
        if value and ("@" not in value or len(value.split("@")) != 2):
            raise ValueError("invalid email")
        return value


class OfferPatch(BaseModel):
    status: str | None = None
    draft_body: str | None = Field(default=None, max_length=8000)

    @field_validator("status")
    @classmethod
    def _status_known(cls, value: str | None) -> str | None:
        if value is not None and value not in VALID_STATUSES:
            raise ValueError("invalid status")
        return value


class OfferImport(BaseModel):
    company_name: str = Field(min_length=1, max_length=_SHORT)
    job_title: str = Field(min_length=1, max_length=500)
    url: str = Field(min_length=8, max_length=2000)
    ats_type: str | None = Field(default=None, max_length=80)
    location: str | None = Field(default=None, max_length=_SHORT)
    description: str | None = Field(default=None, max_length=20000)

    @field_validator("url")
    @classmethod
    def _http_url(cls, value: str) -> str:
        from urllib.parse import urlparse

        parsed = urlparse(value.strip())
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("url must be http or https")
        if parsed.username or parsed.password:
            raise ValueError("url must not contain credentials")
        return value.strip()
