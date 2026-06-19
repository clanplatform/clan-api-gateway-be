import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from app.models.tenant import Tenant
from app.schemas.tenant import TenantCreate, TenantUpdate


class TenantService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, data: TenantCreate) -> Tenant:
        exists = await self.db.execute(select(Tenant).where(Tenant.slug == data.slug))
        if exists.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tenant slug '{data.slug}' already exists",
            )
        tenant = Tenant(
            slug=data.slug,
            name=data.name,
            plan=data.plan,
            metadata_=data.metadata,
        )
        self.db.add(tenant)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def get_by_id(self, tenant_id: uuid.UUID) -> Tenant:
        result = await self.db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    async def get_by_slug(self, slug: str) -> Tenant:
        result = await self.db.execute(select(Tenant).where(Tenant.slug == slug))
        tenant = result.scalar_one_or_none()
        if not tenant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")
        return tenant

    async def list(self, page: int = 1, size: int = 50) -> tuple[list[Tenant], int]:
        offset = (page - 1) * size
        count = await self.db.execute(select(func.count()).select_from(Tenant))
        total = count.scalar_one()
        result = await self.db.execute(
            select(Tenant).offset(offset).limit(size).order_by(Tenant.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(self, tenant_id: uuid.UUID, data: TenantUpdate) -> Tenant:
        tenant = await self.get_by_id(tenant_id)
        changes = data.model_dump(exclude_unset=True)
        for field, value in changes.items():
            # metadata field maps to metadata_ column alias
            setattr(tenant, "metadata_" if field == "metadata" else field, value)
        await self.db.commit()
        await self.db.refresh(tenant)
        return tenant

    async def delete(self, tenant_id: uuid.UUID) -> None:
        tenant = await self.get_by_id(tenant_id)
        await self.db.delete(tenant)
        await self.db.commit()
