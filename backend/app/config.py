from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str

    # Auth
    google_client_id: str
    google_client_secret: str
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    jwt_expiration_hours: int = 168

    # External APIs
    anthropic_api_key: str = ""
    youtube_api_key: str = ""
    siliconflow_api_key: str = ""
    replicate_api_token: str = ""

    # Transcription provider: "siliconflow" or "replicate"
    transcription_provider: str = "replicate"

    # Redis (optional - falls back to in-memory if not configured)
    redis_url: str = ""

    # App Config
    frontend_url: str
    cors_origins: str
    environment: str = "development"

    # Scheduler
    sync_schedule_hour: int = 6
    sync_schedule_minute: int = 0

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
