import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_tenant(client: AsyncClient):
    resp = await client.post("/api/v1/tenants", json={"slug": "acme-corp", "name": "Acme Corp", "plan": "pro"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["slug"] == "acme-corp"
    assert body["plan"] == "pro"
    assert body["is_active"] is True
    assert "id" in body


@pytest.mark.asyncio
async def test_create_tenant_invalid_slug(client: AsyncClient):
    resp = await client.post("/api/v1/tenants", json={"slug": "UPPERCASE", "name": "Bad"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_create_tenant_duplicate_slug(client: AsyncClient):
    payload = {"slug": "dup-tenant", "name": "First"}
    await client.post("/api/v1/tenants", json=payload)
    resp = await client.post("/api/v1/tenants", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_list_tenants_pagination(client: AsyncClient):
    for i in range(3):
        await client.post("/api/v1/tenants", json={"slug": f"list-tenant-{i}", "name": f"T{i}"})
    resp = await client.get("/api/v1/tenants?page=1&size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) <= 2
    assert body["total"] >= 3
    assert body["page"] == 1
    assert body["size"] == 2


@pytest.mark.asyncio
async def test_get_tenant_not_found(client: AsyncClient):
    resp = await client.get("/api/v1/tenants/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_get_tenant(client: AsyncClient):
    create = await client.post("/api/v1/tenants", json={"slug": "get-me", "name": "Get Me"})
    tenant_id = create.json()["id"]
    resp = await client.get(f"/api/v1/tenants/{tenant_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == tenant_id


@pytest.mark.asyncio
async def test_update_tenant(client: AsyncClient):
    create = await client.post("/api/v1/tenants", json={"slug": "update-me", "name": "Before"})
    tenant_id = create.json()["id"]
    resp = await client.patch(f"/api/v1/tenants/{tenant_id}", json={"name": "After", "plan": "enterprise"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "After"
    assert resp.json()["plan"] == "enterprise"


@pytest.mark.asyncio
async def test_delete_tenant(client: AsyncClient):
    create = await client.post("/api/v1/tenants", json={"slug": "delete-me", "name": "Bye"})
    tenant_id = create.json()["id"]
    assert (await client.delete(f"/api/v1/tenants/{tenant_id}")).status_code == 204
    assert (await client.get(f"/api/v1/tenants/{tenant_id}")).status_code == 404


@pytest.mark.asyncio
async def test_health_live(client: AsyncClient):
    resp = await client.get("/api/v1/health/live")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_ready(client: AsyncClient):
    resp = await client.get("/api/v1/health/ready")
    assert resp.status_code == 200
