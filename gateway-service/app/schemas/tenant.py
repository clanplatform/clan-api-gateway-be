import uuid
from datetime import datetime
from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    slug: str = Field(..., min_length=2, max_length=63, pattern=r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")
    name: str = Field(..., min_length=1, max_length=255)
    plan: str = Field(default="starter", pattern=r"^(starter|pro|enterprise)$")
    metadata: dict = Field(default_factory=dict)


class TenantUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    plan: str | None = Field(None, pattern=r"^(starter|pro|enterprise)$")
    is_active: bool | None = None
    metadata: dict | None = None


class TenantResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    plan: str
    is_active: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_model(cls, obj) -> "TenantResponse":
        return cls(
            id=obj.id,
            slug=obj.slug,
            name=obj.name,
            plan=obj.plan,
            is_active=obj.is_active,
            metadata=obj.metadata_ or {},
            created_at=obj.created_at,
            updated_at=obj.updated_at,
        )


class TenantList(BaseModel):
    items: list[TenantResponse]
    total: int
    page: int
    size: int
