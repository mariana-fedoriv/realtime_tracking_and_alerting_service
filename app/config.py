from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = (
        "postgresql+asyncpg://geo:geo@localhost:5432/geo_tracking"
    )
    db_pool_size: int = 10
    db_max_overflow: int = 20
    db_pool_timeout: int = 30

    redis_url: str = "redis://localhost:6379/0"
    redis_ws_channel: str = "ws_events"

    ingest_queue_maxsize: int = 5000
    ingest_worker_count: int = 8

    app_name: str = "real-time-geo-tracking-and-alerting-service"
    debug: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
