import pytest

from app.auth import create_token, decode_token, verify_password


def test_verify_password():
    # Hash for "testpass"
    hashed = "$2b$12$ejQrNFrzPiKryNCQuY251.ZgZqiFr266jQygjSMsBOIL7z09Acv0e"
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


@pytest.mark.asyncio
async def test_login_success(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data


@pytest.mark.asyncio
async def test_login_wrong_password(client, setup_vault):
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "wrongpass"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh(client, setup_vault):
    # Login first
    resp = await client.post("/api/auth/login", json={"username": "admin", "password": "testpass"})
    refresh_token = resp.json()["refresh_token"]

    # Refresh
    resp = await client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
