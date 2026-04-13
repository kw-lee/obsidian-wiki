from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql+asyncpg://obsidian:changeme@db:5432/obsidian_wiki"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # Auth
    jwt_secret: str = "changeme"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    init_admin_username: str = "admin"
    init_admin_password: str = "changeme"

    # Legacy bootstrap-only sync seed values for the first AppSettings row.
    bootstrap_git_remote_url: str = Field(default="", alias="GIT_REMOTE_URL")
    bootstrap_git_branch: str = Field(default="main", alias="GIT_BRANCH")
    bootstrap_git_sync_interval_seconds: int = Field(
        default=300, alias="GIT_SYNC_INTERVAL_SECONDS"
    )

    # Vault
    vault_local_path: str = "/data/vault"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
