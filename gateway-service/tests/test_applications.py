import pytest
import pytest_asyncio
from httpx import AsyncClient


@pytest_asyncio.fixture
async def tenant_id(client: AsyncClient) -> str:
    resp = await client.post("/api/v1/tenants", json={"slug": "app-test-co", "name": "App Test Co"})
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest.mark.asyncio
async def test_create_application_http(client: AsyncClient, tenant_id: str):
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "My API", "slug": "my-api", "upstream_url": "http://backend-svc:8080"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "my-api"
    assert body["upstream_host"] == "backend-svc"
    assert body["upstream_port"] == 8080
    assert body["upstream_tls"] is False


@pytest.mark.asyncio
async def test_create_application_https_upstream(client: AsyncClient, tenant_id: str):
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "Secure API", "slug": "secure-api", "upstream_url": "https://secure-svc:443"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["upstream_tls"] is True
    assert body["upstream_port"] == 443


@pytest.mark.asyncio
async def test_create_application_invalid_upstream(client: AsyncClient, tenant_id: str):
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "Bad", "slug": "bad-app", "upstream_url": "ftp://bad-proto"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_application_duplicate_slug(client: AsyncClient, tenant_id: str):
    payload = {"name": "Dup", "slug": "dup-app", "upstream_url": "http://svc:80"}
    await client.post(f"/api/v1/tenants/{tenant_id}/apps", json=payload)
    resp = await client.post(f"/api/v1/tenants/{tenant_id}/apps", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_applications(client: AsyncClient, tenant_id: str):
    for i in range(3):
        await client.post(
            f"/api/v1/tenants/{tenant_id}/apps",
            json={"name": f"App {i}", "slug": f"app-list-{i}", "upstream_url": f"http://svc{i}:80"},
        )
    resp = await client.get(f"/api/v1/tenants/{tenant_id}/apps")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] >= 3


@pytest.mark.asyncio
async def test_update_application(client: AsyncClient, tenant_id: str):
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "Before", "slug": "upd-app", "upstream_url": "http://old-svc:80"},
    )
    app_id = create.json()["id"]
    resp = await client.patch(
        f"/api/v1/tenants/{tenant_id}/apps/{app_id}",
        json={"name": "After", "upstream_url": "http://new-svc:9000", "rate_limit_rps": 500},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "After"
    assert body["upstream_host"] == "new-svc"
    assert body["upstream_port"] == 9000
    assert body["rate_limit_rps"] == 500


@pytest.mark.asyncio
async def test_delete_application(client: AsyncClient, tenant_id: str):
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "Del", "slug": "del-app", "upstream_url": "http://svc:80"},
    )
    app_id = create.json()["id"]
    assert (await client.delete(f"/api/v1/tenants/{tenant_id}/apps/{app_id}")).status_code == 204
    assert (await client.get(f"/api/v1/tenants/{tenant_id}/apps/{app_id}")).status_code == 404


@pytest.mark.asyncio
async def test_add_route_to_application(client: AsyncClient, tenant_id: str):
    create = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "Route App", "slug": "route-app", "upstream_url": "http://svc:80"},
    )
    app_id = create.json()["id"]
    resp = await client.post(
        f"/api/v1/tenants/{tenant_id}/apps/{app_id}/routes",
        json={"path_prefix": "/api/v2", "methods": ["GET", "POST"], "timeout_ms": 15000},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["path_prefix"] == "/api/v2"
    assert body["timeout_ms"] == 15000


@pytest.mark.asyncio
async def test_xds_cluster_discovery(client: AsyncClient, tenant_id: str):
    await client.post(
        f"/api/v1/tenants/{tenant_id}/apps",
        json={"name": "XDS App", "slug": "xds-app", "upstream_url": "http://xds-backend:8080"},
    )
    resp = await client.post("/xds/v3/discovery:clusters", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "version_info" in body
    assert "resources" in body
    cluster_names = [r["name"] for r in body["resources"]]
    assert any("xds-app" in name or len(name) > 10 for name in cluster_names)


@pytest.mark.asyncio
async def test_xds_route_discovery(client: AsyncClient):
    resp = await client.post("/xds/v3/discovery:routes", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert "resources" in body
    assert body["type_url"] == "type.googleapis.com/envoy.config.route.v3.RouteConfiguration"
