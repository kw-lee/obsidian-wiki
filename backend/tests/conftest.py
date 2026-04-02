import os

# Override settings before any app imports
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///test.db"
os.environ["REDIS_URL"] = "redis://localhost:6379/15"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD_HASH"] = (
    "$2b$12$ejQrNFrzPiKryNCQuY251.ZgZqiFr266jQygjSMsBOIL7z09Acv0e"  # "testpass"
)
os.environ["VAULT_LOCAL_PATH"] = "/tmp/test_vault"

import shutil
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.auth import create_token


@pytest.fixture(autouse=True)
def setup_vault(tmp_path: Path):
    vault = tmp_path / "vault"
    vault.mkdir()
    os.environ["VAULT_LOCAL_PATH"] = str(vault)
    # Re-set the settings
    from app.config import settings

    settings.vault_local_path = str(vault)
    yield vault
    shutil.rmtree(vault, ignore_errors=True)


@pytest.fixture
def auth_headers():
    token = create_token("admin", "access")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
