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
    admin_username: str = "admin"
    admin_password_hash: str = ""

    # Git
    git_remote_url: str = ""
    git_branch: str = "main"
    git_sync_interval_seconds: int = 300

    # Vault
    vault_local_path: str = "/data/vault"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
