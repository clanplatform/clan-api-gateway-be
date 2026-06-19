import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.tenant_service import TenantService
from app.schemas.tenant import TenantCreate, TenantUpdate, TenantResponse, TenantList

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.post("", response_model=TenantResponse, status_code=201)
async def create_tenant(data: TenantCreate, db: AsyncSession = Depends(get_db)) -> TenantResponse:
    tenant = await TenantService(db).create(data)
    return TenantResponse.from_model(tenant)


@router.get("", response_model=TenantList)
async def list_tenants(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> TenantList:
    tenants, total = await TenantService(db).list(page=page, size=size)
    return TenantList(
        items=[TenantResponse.from_model(t) for t in tenants],
        total=total,
        page=page,
        size=size,
    )


@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> TenantResponse:
    tenant = await TenantService(db).get_by_id(tenant_id)
    return TenantResponse.from_model(tenant)


@router.patch("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(
    tenant_id: uuid.UUID, data: TenantUpdate, db: AsyncSession = Depends(get_db)
) -> TenantResponse:
    tenant = await TenantService(db).update(tenant_id, data)
    return TenantResponse.from_model(tenant)


@router.delete("/{tenant_id}", status_code=204)
async def delete_tenant(tenant_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    await TenantService(db).delete(tenant_id)
