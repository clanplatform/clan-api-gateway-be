"""
Internal sync endpoint — called by clan-platform-domain-be to push tenant data
into clan-api-gateway-be when a tenant is created or updated.

Protected by X-Internal-API-Key header.
"""
import re
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.core.database import get_db
from app.core.config import get_settings
from app.models.tenant import Tenant
from app.schemas.tenant import TenantSyncPayload, TenantResponse

router = APIRouter(prefix="/sync", tags=["sync (internal)"])
settings = get_settings()


def _verify_internal_key(x_internal_api_key: str = Header(...)):
    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid internal API key")


def _to_slug(tenant_code: str | None, tenant_name: str) -> str:
    """Derive a valid slug from tenant_code or tenant_name."""
    raw = tenant_code or tenant_name
    slug = re.sub(r"[^a-z0-9]+", "-", raw.lower()).strip("-")
    if len(slug) < 2:
        slug = slug + "-tenant"
    return slug[:63]


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_200_OK,
    summary="Upsert gateway tenant from platform-domain (tenant created/updated)",
    dependencies=[Depends(_verify_internal_key)],
)
async def sync_tenant(
    payload: TenantSyncPayload,
    db: AsyncSession = Depends(get_db),
) -> TenantResponse:
    """
    clan-platform-domain-be calls this after creating or updating a tenant.
    Upserts the gateway Tenant row keyed by admin_tenant_id so Envoy routing
    stays in sync with the platform-domain tenant registry.
    """
    plan_map = {"basic": "starter", "pro": "pro", "enterprise": "enterprise"}
    plan = plan_map.get((payload.subscription_plan or "").lower(), "starter")

    # Try to find existing row by admin_tenant_id
    result = await db.execute(select(Tenant).where(Tenant.admin_tenant_id == payload.tenant_id))
    existing = result.scalar_one_or_none()

    if existing:
        existing.name      = payload.tenant_name
        existing.plan      = plan
        existing.is_active = payload.is_active
        await db.commit()
        await db.refresh(existing)
        return TenantResponse.from_model(existing)

    slug = _to_slug(payload.tenant_code, payload.tenant_name)

    # Ensure slug uniqueness — append suffix if taken
    check = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if check.scalar_one_or_none():
        slug = f"{slug}-{str(payload.tenant_id)[:8]}"

    tenant = Tenant(
        admin_tenant_id = payload.tenant_id,
        slug            = slug,
        name            = payload.tenant_name,
        plan            = plan,
        is_active       = payload.is_active,
    )
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return TenantResponse.from_model(tenant)
