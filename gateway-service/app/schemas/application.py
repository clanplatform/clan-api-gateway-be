import uuid
from datetime import datetime
from urllib.parse import urlparse
from pydantic import BaseModel, Field, model_validator


class ApplicationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str = Field(..., min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    upstream_url: str = Field(..., description="Full upstream base URL, e.g. http://svc:8080")
    rate_limit_rps: int = Field(default=100, ge=1, le=100_000)
    rate_limit_burst: int = Field(default=200, ge=1, le=200_000)
    cors_origins: list[str] = Field(default_factory=list)
    jwt_required: bool = True
    config: dict = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_upstream(self) -> "ApplicationCreate":
        parsed = urlparse(self.upstream_url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("upstream_url must use http or https scheme")
        if not parsed.hostname:
            raise ValueError("upstream_url must include a hostname")
        return self


class ApplicationUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    upstream_url: str | None = None
    rate_limit_rps: int | None = Field(None, ge=1, le=100_000)
    rate_limit_burst: int | None = Field(None, ge=1, le=200_000)
    cors_origins: list[str] | None = None
    jwt_required: bool | None = None
    is_active: bool | None = None
    config: dict | None = None


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    tenant_id: uuid.UUID
    name: str
    slug: str
    upstream_url: str
    upstream_host: str
    upstream_port: int
    upstream_tls: bool
    rate_limit_rps: int
    rate_limit_burst: int
    cors_origins: list[str]
    jwt_required: bool
    is_active: bool
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ApplicationList(BaseModel):
    items: list[ApplicationResponse]
    total: int
    page: int
    size: int
