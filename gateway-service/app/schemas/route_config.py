import uuid
from datetime import datetime
from pydantic import BaseModel, Field

_HTTP_METHODS = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}


class RouteConfigCreate(BaseModel):
    path_prefix: str = Field(..., min_length=1, max_length=512, pattern=r"^/.*")
    methods: list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"]
    )
    strip_prefix: bool = False
    prefix_rewrite: str | None = Field(None, max_length=512)
    timeout_ms: int = Field(default=30_000, ge=100, le=300_000)
    retry_attempts: int = Field(default=3, ge=0, le=10)
    priority: int = Field(default=0, ge=0, le=100)
    headers_to_add: dict[str, str] = Field(default_factory=dict)


class RouteConfigUpdate(BaseModel):
    methods: list[str] | None = None
    strip_prefix: bool | None = None
    prefix_rewrite: str | None = None
    timeout_ms: int | None = Field(None, ge=100, le=300_000)
    retry_attempts: int | None = Field(None, ge=0, le=10)
    priority: int | None = Field(None, ge=0, le=100)
    headers_to_add: dict[str, str] | None = None


class RouteConfigResponse(BaseModel):
    id: uuid.UUID
    application_id: uuid.UUID
    path_prefix: str
    methods: list[str]
    strip_prefix: bool
    prefix_rewrite: str | None
    timeout_ms: int
    retry_attempts: int
    priority: int
    headers_to_add: dict
    created_at: datetime

    model_config = {"from_attributes": True}
