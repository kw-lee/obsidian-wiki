import pytest

from app.auth import create_token, decode_token, hash_password, verify_password


def test_verify_password():
    hashed = hash_password("testpass")
    assert verify_password("testpass", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_create_and_decode_token():
    token = create_token(1, "access", username="admin")
    payload = decode_token(token)
    assert payload["sub"] == "1"
    assert payload["username"] == "admin"
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
    assert data["username"] == "admin"
    assert "refresh_token" not in data
    # Initial user must change credentials
    assert data["must_change_credentials"] is True
    assert "httponly" in resp.headers["set-cookie"].lower()


@pytest.mark.asyncio
async def test_login_wrong_password(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    resp = await client.post("/api/auth/refresh")
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert resp.json()["username"] == "admin"


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
        json={
            "new_username": "myuser",
            "new_password": "Newpass123!A",
            "git_display_name": "My User",
            "git_email": "myuser@example.com",
        },
        headers=headers,
    )
    assert resp.status_code == 200
    new_data = resp.json()
    assert new_data["must_change_credentials"] is False
    assert new_data["username"] == "myuser"
    new_token = new_data["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    # 3. Now can access normal API with new token
    resp = await client.get("/api/wiki/tree", headers=new_headers)
    assert resp.status_code == 200

    # 4. Login with new credentials works
    resp = await client.post(
        "/api/auth/login", json={"username": "myuser", "password": "Newpass123!A"}
    )
    assert resp.status_code == 200
    assert resp.json()["must_change_credentials"] is False

    # 5. Old credentials no longer work
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_change_credentials_rejects_weak_password(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = await client.post(
        "/api/auth/change-credentials",
        json={
            "new_username": "myuser",
            "new_password": "short",
            "git_display_name": "My User",
            "git_email": "myuser@example.com",
        },
        headers=headers,
    )
    assert resp.status_code == 400
    assert "password" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_login_rate_limit(client, monkeypatch, setup_vault):
    from app.services import rate_limit

    async def fail_redis_count(key: str):
        raise RuntimeError(key)

    async def fail_redis_hit(key: str, *, window_seconds: int):
        raise RuntimeError(f"{key}:{window_seconds}")

    monkeypatch.setattr(rate_limit, "_redis_count", fail_redis_count)
    monkeypatch.setattr(rate_limit, "_redis_hit", fail_redis_hit)

    for _ in range(10):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "wrongpass"},
        )
        assert resp.status_code == 401

    blocked = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "wrongpass"},
    )
    assert blocked.status_code == 429


@pytest.mark.asyncio
async def test_logout_clears_refresh_cookie(client, setup_vault):
    login = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert login.status_code == 200

    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 204
    assert "max-age=0" in resp.headers["set-cookie"].lower()
