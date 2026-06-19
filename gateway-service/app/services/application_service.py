import uuid
from urllib.parse import urlparse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from app.models.application import Application
from app.models.route_config import RouteConfig
from app.schemas.application import ApplicationCreate, ApplicationUpdate
from app.schemas.route_config import RouteConfigCreate, RouteConfigUpdate
from app.services.xds_service import XdsService


class ApplicationService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create(self, tenant_id: uuid.UUID, data: ApplicationCreate) -> Application:
        parsed = urlparse(data.upstream_url)
        host = parsed.hostname or ""
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        tls = parsed.scheme == "https"

        dup = await self.db.execute(
            select(Application).where(
                Application.tenant_id == tenant_id, Application.slug == data.slug
            )
        )
        if dup.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"App slug '{data.slug}' already exists for this tenant",
            )

        app = Application(
            tenant_id=tenant_id,
            name=data.name,
            slug=data.slug,
            upstream_url=data.upstream_url,
            upstream_host=host,
            upstream_port=port,
            upstream_tls=tls,
            rate_limit_rps=data.rate_limit_rps,
            rate_limit_burst=data.rate_limit_burst,
            cors_origins=data.cors_origins,
            jwt_required=data.jwt_required,
            config=data.config,
        )
        self.db.add(app)
        await self.db.flush()

        # Default catch-all route — every app gets one automatically
        self.db.add(RouteConfig(application_id=app.id, path_prefix="/"))
        await self.db.commit()
        await self.db.refresh(app)
        await XdsService.bump_version()
        return app

    async def get_by_id(self, app_id: uuid.UUID, tenant_id: uuid.UUID | None = None) -> Application:
        q = select(Application).where(Application.id == app_id)
        if tenant_id is not None:
            q = q.where(Application.tenant_id == tenant_id)
        result = await self.db.execute(q)
        app = result.scalar_one_or_none()
        if not app:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")
        return app

    async def list(
        self, tenant_id: uuid.UUID, page: int = 1, size: int = 50
    ) -> tuple[list[Application], int]:
        offset = (page - 1) * size
        count = await self.db.execute(
            select(func.count()).select_from(Application).where(Application.tenant_id == tenant_id)
        )
        total = count.scalar_one()
        result = await self.db.execute(
            select(Application)
            .where(Application.tenant_id == tenant_id)
            .offset(offset)
            .limit(size)
            .order_by(Application.created_at.desc())
        )
        return list(result.scalars().all()), total

    async def update(
        self, app_id: uuid.UUID, tenant_id: uuid.UUID, data: ApplicationUpdate
    ) -> Application:
        app = await self.get_by_id(app_id, tenant_id)
        changes = data.model_dump(exclude_unset=True)
        if "upstream_url" in changes:
            parsed = urlparse(changes["upstream_url"])
            changes["upstream_host"] = parsed.hostname or ""
            changes["upstream_port"] = parsed.port or (443 if parsed.scheme == "https" else 80)
            changes["upstream_tls"] = parsed.scheme == "https"
        for field, value in changes.items():
            setattr(app, field, value)
        await self.db.commit()
        await self.db.refresh(app)
        await XdsService.bump_version()
        return app

    async def delete(self, app_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
        app = await self.get_by_id(app_id, tenant_id)
        await self.db.delete(app)
        await self.db.commit()
        await XdsService.bump_version()

    # ── Route management ─────────────────────────────────────────────────────

    async def add_route(
        self, app_id: uuid.UUID, tenant_id: uuid.UUID, data: RouteConfigCreate
    ) -> RouteConfig:
        await self.get_by_id(app_id, tenant_id)
        route = RouteConfig(application_id=app_id, **data.model_dump())
        self.db.add(route)
        await self.db.commit()
        await self.db.refresh(route)
        await XdsService.bump_version()
        return route

    async def update_route(
        self, route_id: uuid.UUID, app_id: uuid.UUID, data: RouteConfigUpdate
    ) -> RouteConfig:
        result = await self.db.execute(
            select(RouteConfig).where(
                RouteConfig.id == route_id, RouteConfig.application_id == app_id
            )
        )
        route = result.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        for field, value in data.model_dump(exclude_unset=True).items():
            setattr(route, field, value)
        await self.db.commit()
        await self.db.refresh(route)
        await XdsService.bump_version()
        return route

    async def delete_route(self, route_id: uuid.UUID, app_id: uuid.UUID) -> None:
        result = await self.db.execute(
            select(RouteConfig).where(
                RouteConfig.id == route_id, RouteConfig.application_id == app_id
            )
        )
        route = result.scalar_one_or_none()
        if not route:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Route not found")
        await self.db.delete(route)
        await self.db.commit()
        await XdsService.bump_version()
