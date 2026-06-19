"""
Seed script: registers clan-identity-be and clan-platform-domain-be services
in the API gateway database as a "clan" tenant with upstream applications.

Usage (from the gateway-service directory):
    python scripts/seed_services.py

Environment variables (or edit defaults below):
    DATABASE_URL  — async postgres URL (default matches docker-compose dev)
    ADMIN_SERVICE_PORT — host port for platform-admin (default 8000; the
                         gateway-service control plane moved to 8010 so there
                         is no longer a port conflict)

Port mapping (all services reachable via host.docker.internal from Envoy):
    clan-identity-be
        auth-service     -> 8001  (/api/v1/login, /api/v1/auth/users, /api/v1/sync)
        user-service     -> 8002  (/api/v1/auth)
        session-service  -> 8003  (/api/v1/sessions)
        rbac-service     -> 8004  (/api/v1/rbac)
        oauth-service    -> 8005  (/api/v1/oauth)
    clan-platform-domain-be
        admin-service    -> 8000  (/api/v1/domains, /api/v1/applications, …)
                           gateway-service control plane is on 8010, so no
                           conflict with admin-service staying on 8000.
"""
import asyncio
import os
import sys
import uuid
from urllib.parse import urlparse

# Allow running from the gateway-service root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://postgres:postgres@localhost:5434/api_gateway",
)
# admin-service (platform-domain-be) runs on host port 8000;
# gateway-service control plane is now on 8010, so no conflict.
ADMIN_SERVICE_PORT = int(os.getenv("ADMIN_SERVICE_PORT", "8000"))

# ---------------------------------------------------------------------------
# Service definitions
# ---------------------------------------------------------------------------
# Each entry: name, slug, upstream URL, jwt_required, cors_origins, routes[]
# Routes are ordered longest-prefix-first so that Envoy prefix matching is
# unambiguous even if this script is re-run and ordering in DB shifts.
# ---------------------------------------------------------------------------
TENANT = {
    "slug": "clan",
    "name": "Clan Platform",
    "plan": "enterprise",
}

SERVICES = [
    {
        "name": "Identity Auth Service",
        "slug": "identity-auth",
        "upstream_url": "http://host.docker.internal:8001",
        "jwt_required": False,  # auth endpoints issue tokens — no JWT gate here
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": [
            # longest prefixes first to guarantee correct Envoy matching
            "/api/v1/auth/users",
            "/api/v1/login",
            "/api/v1/sync",
        ],
    },
    {
        "name": "Identity User Service",
        "slug": "identity-user",
        "upstream_url": "http://host.docker.internal:8002",
        "jwt_required": True,
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": ["/api/v1/auth"],
    },
    {
        "name": "Identity Session Service",
        "slug": "identity-session",
        "upstream_url": "http://host.docker.internal:8003",
        "jwt_required": True,
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": ["/api/v1/sessions"],
    },
    {
        "name": "Identity RBAC Service",
        "slug": "identity-rbac",
        "upstream_url": "http://host.docker.internal:8004",
        "jwt_required": True,
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": ["/api/v1/rbac"],
    },
    {
        "name": "Identity OAuth Service",
        "slug": "identity-oauth",
        "upstream_url": "http://host.docker.internal:8005",
        "jwt_required": False,
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": ["/api/v1/oauth"],
    },
    {
        "name": "Platform Admin Service",
        "slug": "platform-admin",
        "upstream_url": f"http://host.docker.internal:{ADMIN_SERVICE_PORT}",
        "jwt_required": True,
        "cors_origins": ["http://localhost:3000", "http://localhost:8080"],
        "routes": [
            # longer prefixes before shorter overlapping ones
            "/api/v1/user_role_form_permission",
            "/api/v1/menus_language",
            "/api/v1/forms_language",
            "/api/v1/user_setup",
            "/api/v1/user_role",
            "/api/v1/departments",
            "/api/v1/applications",
            "/api/v1/job_codes",
            "/api/v1/divisions",
            "/api/v1/domains",
            "/api/v1/modules",
            "/api/v1/clients",
            "/api/v1/entity",
            "/api/v1/menus",
            "/api/v1/forms",
        ],
    },
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_upstream(url: str) -> tuple[str, int, bool]:
    parsed = urlparse(url)
    host = parsed.hostname or ""
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    tls = parsed.scheme == "https"
    return host, port, tls


async def _get_or_create_tenant(session: AsyncSession, data: dict):
    from app.models.tenant import Tenant

    result = await session.execute(
        select(Tenant).where(Tenant.slug == data["slug"])
    )
    tenant = result.scalar_one_or_none()
    if tenant:
        print(f"  Tenant '{data['slug']}' already exists — skipping creation")
        return tenant

    tenant = Tenant(
        slug=data["slug"],
        name=data["name"],
        plan=data.get("plan", "starter"),
        is_active=True,
    )
    session.add(tenant)
    await session.flush()
    print(f"  Created tenant '{tenant.slug}' ({tenant.id})")
    return tenant


async def _get_or_create_application(session: AsyncSession, tenant_id: uuid.UUID, svc: dict):
    from app.models.application import Application
    from app.models.route_config import RouteConfig

    result = await session.execute(
        select(Application).where(
            Application.tenant_id == tenant_id,
            Application.slug == svc["slug"],
        )
    )
    app = result.scalar_one_or_none()
    if app:
        print(f"    App '{svc['slug']}' already exists — skipping")
        return app

    host, port, tls = _parse_upstream(svc["upstream_url"])
    app = Application(
        tenant_id=tenant_id,
        name=svc["name"],
        slug=svc["slug"],
        upstream_url=svc["upstream_url"],
        upstream_host=host,
        upstream_port=port,
        upstream_tls=tls,
        jwt_required=svc.get("jwt_required", True),
        cors_origins=svc.get("cors_origins", []),
        rate_limit_rps=500,
        rate_limit_burst=1000,
    )
    session.add(app)
    await session.flush()

    for idx, prefix in enumerate(svc["routes"]):
        session.add(
            RouteConfig(
                application_id=app.id,
                path_prefix=prefix,
                priority=idx,  # lower index -> higher priority (shorter sort key)
            )
        )

    print(f"    Created app '{app.slug}' -> {svc['upstream_url']}")
    for prefix in svc["routes"]:
        print(f"      route: {prefix}")
    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    AsyncSessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Ensure tables exist (idempotent)
    from app.core.database import Base
    import app.models.tenant  # noqa: F401 — registers models with Base
    import app.models.application  # noqa: F401
    import app.models.route_config  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        async with session.begin():
            print("\n=== Seeding clan tenant ===")
            tenant = await _get_or_create_tenant(session, TENANT)

            print("\n=== Registering upstream services ===")
            for svc in SERVICES:
                print(f"\n  [{svc['slug']}]")
                await _get_or_create_application(session, tenant.id, svc)

    await engine.dispose()
    print("\nDone. Restart the gateway-service (or wait for xDS refresh) to pick up changes.")


if __name__ == "__main__":
    asyncio.run(seed())
