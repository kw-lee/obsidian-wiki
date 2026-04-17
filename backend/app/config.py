import json
from typing import Annotated
from typing import Any
from urllib.parse import urlparse

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode

_PRODUCTION_ENVS = {"prod", "production"}
_DEV_CORS_ALLOWED_ORIGINS = [
    "http://localhost",
    "http://127.0.0.1",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]
_PLACEHOLDER_VALUES = {
    "changeme",
    "change-me",
    "replace-me",
    "replace_me",
    "password",
    "secret",
    "your-secret-here",
    "your-secret",
}


class Settings(BaseSettings):
    app_env: str = Field(default="development", alias="APP_ENV")

    # Database
    database_url: str = "postgresql+asyncpg://obsidian:changeme@db:5432/obsidian_wiki"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Auth
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    refresh_cookie_name: str = "obsidian_wiki_refresh"
    init_admin_username: str = "admin"
    init_admin_password: str = "changeme"
    app_timezone: str = Field(default="Asia/Seoul", alias="APP_TIMEZONE")
    allow_private_sync_targets: bool = Field(default=False, alias="ALLOW_PRIVATE_SYNC_TARGETS")
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias="CORS_ALLOWED_ORIGINS"
    )
    auth_rate_limit_window_seconds: int = Field(default=300, alias="AUTH_RATE_LIMIT_WINDOW_SECONDS")
    auth_rate_limit_max_attempts: int = Field(default=10, alias="AUTH_RATE_LIMIT_MAX_ATTEMPTS")
    auth_password_min_length: int = Field(default=12, alias="AUTH_PASSWORD_MIN_LENGTH")

    # Legacy bootstrap-only sync seed values for the first AppSettings row.
    bootstrap_git_remote_url: str = Field(default="", alias="GIT_REMOTE_URL")
    bootstrap_git_branch: str = Field(default="main", alias="GIT_BRANCH")
    bootstrap_git_sync_interval_seconds: int = Field(default=300, alias="GIT_SYNC_INTERVAL_SECONDS")

    # Vault
    vault_local_path: str = "/data/vault"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def _parse_cors_allowed_origins(cls, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return []
            if text.startswith("["):
                try:
                    decoded = json.loads(text)
                except json.JSONDecodeError:
                    decoded = None
                if isinstance(decoded, list):
                    return [str(item).strip() for item in decoded if str(item).strip()]
            return [item.strip() for item in text.split(",") if item.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]

        raise TypeError("CORS_ALLOWED_ORIGINS must be a list or comma-separated string")

    @property
    def is_production(self) -> bool:
        return self.app_env.strip().lower() in _PRODUCTION_ENVS

    @property
    def resolved_cors_allowed_origins(self) -> list[str]:
        if self.cors_allowed_origins:
            return list(self.cors_allowed_origins)
        if self.is_production:
            return []
        return list(_DEV_CORS_ALLOWED_ORIGINS)


def build_cors_middleware_options(current: Settings) -> dict[str, object]:
    return {
        "allow_origins": current.resolved_cors_allowed_origins,
        "allow_credentials": True,
        "allow_methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Authorization", "Content-Type"],
    }


def validate_runtime_settings(current: Settings) -> None:
    if not current.is_production:
        return

    errors: list[str] = []

    jwt_secret = current.jwt_secret.strip()
    if len(jwt_secret) < 32 or _looks_like_placeholder(jwt_secret):
        errors.append("JWT_SECRET must be at least 32 characters and not use a placeholder value")

    admin_username = current.init_admin_username.strip()
    if not admin_username:
        errors.append("INIT_ADMIN_USERNAME is required in production")

    admin_password = current.init_admin_password.strip()
    if len(admin_password) < 12 or _looks_like_placeholder(admin_password):
        errors.append(
            "INIT_ADMIN_PASSWORD must be at least 12 characters and not use a placeholder value"
        )

    database_password = _extract_database_password(current.database_url)
    if database_password is None:
        errors.append("DATABASE_URL must include a password in production")
    elif len(database_password) < 8 or _looks_like_placeholder(database_password):
        errors.append(
            "DATABASE_URL must include a non-placeholder password with at least 8 characters"
        )

    if not current.cors_allowed_origins:
        errors.append("CORS_ALLOWED_ORIGINS must be explicitly set in production")
    elif "*" in current.cors_allowed_origins:
        errors.append("CORS_ALLOWED_ORIGINS cannot include '*' in production")

    if errors:
        raise RuntimeError("Insecure production configuration:\n- " + "\n- ".join(errors))


def _extract_database_password(database_url: str) -> str | None:
    parsed = urlparse(database_url.strip())
    if parsed.scheme.startswith("sqlite"):
        return None
    return parsed.password


def _looks_like_placeholder(value: str) -> bool:
    normalized = value.strip().lower()
    if not normalized:
        return True
    if normalized in _PLACEHOLDER_VALUES:
        return True
    return normalized.startswith(
        (
            "changeme",
            "change-me",
            "change_me",
            "replace-me",
            "replace_me",
        )
    )


settings = Settings()
