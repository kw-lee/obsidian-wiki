import pytest

from app.config import Settings, build_cors_middleware_options, validate_runtime_settings


def _make_settings(**overrides) -> Settings:
    settings = Settings()
    settings.app_env = "development"
    settings.database_url = (
        "postgresql+asyncpg://obsidian:very-strong-db-password@db:5432/obsidian_wiki"
    )
    settings.jwt_secret = "a" * 32
    settings.init_admin_username = "owner"
    settings.init_admin_password = "very-strong-admin-password"
    settings.cors_allowed_origins = []
    settings.vault_local_path = "/tmp/test-vault"

    for key, value in overrides.items():
        setattr(settings, key, value)

    return settings


def test_build_cors_middleware_uses_local_dev_allowlist_by_default():
    config = build_cors_middleware_options(_make_settings())

    assert config["allow_credentials"] is True
    assert config["allow_methods"] == ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
    assert config["allow_headers"] == ["Authorization", "Content-Type"]
    assert "http://localhost" in config["allow_origins"]
    assert "http://localhost:5173" in config["allow_origins"]
    assert "*" not in config["allow_origins"]


def test_cors_allowed_origins_accepts_comma_separated_env_values():
    assert Settings._parse_cors_allowed_origins(  # noqa: SLF001
        "https://wiki.example.com, https://notes.example.com"
    ) == [
        "https://wiki.example.com",
        "https://notes.example.com",
    ]


def test_cors_allowed_origins_accepts_empty_env_value():
    assert Settings._parse_cors_allowed_origins("") == []  # noqa: SLF001


def test_validate_runtime_settings_rejects_insecure_production_defaults():
    settings = _make_settings(
        app_env="production",
        database_url="postgresql+asyncpg://obsidian:changeme@db:5432/obsidian_wiki",
        jwt_secret="changeme_generate_with_openssl_rand",
        init_admin_password="changeme",
        cors_allowed_origins=[],
    )

    with pytest.raises(RuntimeError) as exc_info:
        validate_runtime_settings(settings)

    message = str(exc_info.value)
    assert "JWT_SECRET" in message
    assert "INIT_ADMIN_PASSWORD" in message
    assert "DATABASE_URL" in message
    assert "CORS_ALLOWED_ORIGINS" in message


def test_validate_runtime_settings_rejects_wildcard_cors_in_production():
    settings = _make_settings(app_env="production", cors_allowed_origins=["*"])

    with pytest.raises(RuntimeError, match="CORS_ALLOWED_ORIGINS cannot include '\\*'"):
        validate_runtime_settings(settings)


def test_validate_runtime_settings_accepts_strong_production_values():
    settings = _make_settings(
        app_env="production",
        database_url="postgresql+asyncpg://obsidian:very-strong-db-password@db:5432/obsidian_wiki",
        jwt_secret="super-secret-jwt-key-with-32-plus-chars",
        init_admin_password="replace-this-admin-password-now",
        cors_allowed_origins=["https://wiki.example.com"],
    )

    validate_runtime_settings(settings)
