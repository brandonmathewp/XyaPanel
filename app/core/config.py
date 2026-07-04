"""Application configuration loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # MongoDB
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "xya_panel"

    # Redis / Celery
    redis_url: str = "redis://localhost:6379/0"

    # Security
    master_secret: str = "change-me"
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_minutes: int = 1440  # 24 hours

    # Admin bootstrap
    admin_email: str = "admin@xya.local"
    admin_password_hash: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000

    # License validation rate limit (requests per window per IP)
    validation_rate_limit: int = 30
    validation_rate_window_seconds: int = 60


settings = Settings()
