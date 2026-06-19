import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services.application_service import ApplicationService
from app.schemas.application import ApplicationCreate, ApplicationUpdate, ApplicationResponse, ApplicationList
from app.schemas.route_config import RouteConfigCreate, RouteConfigUpdate, RouteConfigResponse

router = APIRouter(prefix="/tenants/{tenant_id}/apps", tags=["applications"])


@router.post("", response_model=ApplicationResponse, status_code=201)
async def create_application(
    tenant_id: uuid.UUID, data: ApplicationCreate, db: AsyncSession = Depends(get_db)
) -> ApplicationResponse:
    return await ApplicationService(db).create(tenant_id, data)


@router.get("", response_model=ApplicationList)
async def list_applications(
    tenant_id: uuid.UUID,
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
) -> ApplicationList:
    apps, total = await ApplicationService(db).list(tenant_id, page=page, size=size)
    return ApplicationList(items=apps, total=total, page=page, size=size)


@router.get("/{app_id}", response_model=ApplicationResponse)
async def get_application(
    tenant_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> ApplicationResponse:
    return await ApplicationService(db).get_by_id(app_id, tenant_id)


@router.patch("/{app_id}", response_model=ApplicationResponse)
async def update_application(
    tenant_id: uuid.UUID,
    app_id: uuid.UUID,
    data: ApplicationUpdate,
    db: AsyncSession = Depends(get_db),
) -> ApplicationResponse:
    return await ApplicationService(db).update(app_id, tenant_id, data)


@router.delete("/{app_id}", status_code=204)
async def delete_application(
    tenant_id: uuid.UUID, app_id: uuid.UUID, db: AsyncSession = Depends(get_db)
) -> None:
    await ApplicationService(db).delete(app_id, tenant_id)


@router.post("/{app_id}/routes", response_model=RouteConfigResponse, status_code=201)
async def add_route(
    tenant_id: uuid.UUID,
    app_id: uuid.UUID,
    data: RouteConfigCreate,
    db: AsyncSession = Depends(get_db),
) -> RouteConfigResponse:
    return await ApplicationService(db).add_route(app_id, tenant_id, data)


@router.patch("/{app_id}/routes/{route_id}", response_model=RouteConfigResponse)
async def update_route(
    tenant_id: uuid.UUID,
    app_id: uuid.UUID,
    route_id: uuid.UUID,
    data: RouteConfigUpdate,
    db: AsyncSession = Depends(get_db),
) -> RouteConfigResponse:
    return await ApplicationService(db).update_route(route_id, app_id, data)


@router.delete("/{app_id}/routes/{route_id}", status_code=204)
async def delete_route(
    tenant_id: uuid.UUID,
    app_id: uuid.UUID,
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    await ApplicationService(db).delete_route(route_id, app_id)
