import pytest

from app.auth import create_token, decode_token, hash_password, verify_password


def test_verify_password():
    hashed = hash_password("testpass")
    assert verify_password("testpass", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_decode_token():
    token = create_token("admin", "access")
    payload = decode_token(token)
    assert payload["sub"] == "admin"
    assert payload["type"] == "access"


def test_refresh_token():
    token = create_token("admin", "refresh")
    payload = decode_token(token)
    assert payload["type"] == "refresh"


def test_must_change_token():
    token = create_token("admin", "access", must_change=True)
    payload = decode_token(token)
    assert payload["must_change"] is True


def test_no_must_change_by_default():
    token = create_token("admin", "access")
    payload = decode_token(token)
    assert "must_change" not in payload


# ── Integration tests ────────────────────────────────


@pytest.mark.asyncio
async def test_login_success(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    # Initial user must change credentials
    assert data["must_change_credentials"] is True


@pytest.mark.asyncio
async def test_login_wrong_password(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    refresh_token = resp.json()["refresh_token"]

    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()


@pytest.mark.asyncio
async def test_must_change_blocks_api(client, setup_vault):
    """must_change=true token should be blocked from normal API access."""
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.get("/api/wiki/tree", headers=headers)
    assert resp.status_code == 403
    assert "Credential change required" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_change_credentials_flow(client, setup_vault):
    """Full flow: login → must_change → change credentials → normal access."""
    # 1. Login with initial credentials
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["must_change_credentials"] is True
    token = data["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Change credentials
    resp = await client.post(
        "/api/auth/change-credentials",
        json={"new_username": "myuser", "new_password": "newpass123"},
        headers=headers,
    )
    assert resp.status_code == 200
    new_data = resp.json()
    assert new_data["must_change_credentials"] is False
    new_token = new_data["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 3. Now can access normal API with new token
    resp = await client.get("/api/wiki/tree", headers=new_headers)
    assert resp.status_code == 200

    # 4. Login with new credentials works
    resp = await client.post("/api/auth/login", json={"username": "myuser", "password": "newpass123"})
    assert resp.status_code == 200
    assert resp.json()["must_change_credentials"] is False

    # 5. Old credentials no longer work
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 401
