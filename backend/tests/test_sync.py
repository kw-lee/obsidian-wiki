import pytest


@pytest.mark.asyncio
async def test_sync_status(client, auth_headers, setup_vault):
    resp = await client.get("/api/sync/status", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "ahead" in data
    assert "behind" in data
    assert "dirty" in data


@pytest.mark.asyncio
async def test_sync_requires_auth(client, setup_vault):
    resp = await client.get("/api/sync/status")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/pull")
    assert resp.status_code in (401, 403)

    resp = await client.post("/api/sync/push")
    assert resp.status_code in (401, 403)
