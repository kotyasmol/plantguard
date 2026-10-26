from functools import lru_cache
from pathlib import Path
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEVELOPMENT_PHOTO_SIGNING_KEY = "development-only-photo-signing-key"


class Settings(BaseSettings):
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    database_url: str = "postgresql+psycopg://plantguard:plantguard@localhost:5432/plantguard"
    max_image_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    max_image_pixels: int = Field(default=25_000_000, gt=0)
    photo_storage_path: Path = Path(".data/photos")
    photo_url_ttl_seconds: int = Field(default=15 * 60, gt=0, le=24 * 60 * 60)
    photo_signing_key: str = Field(default=DEVELOPMENT_PHOTO_SIGNING_KEY, min_length=32)
    web_dist_path: Optional[Path] = None

    model_config = SettingsConfigDict(env_prefix="PLANTGUARD_", env_file=".env")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def require_production_photo_signing_key(self) -> "Settings":
        if (
            self.environment == "production"
            and self.photo_signing_key == DEVELOPMENT_PHOTO_SIGNING_KEY
        ):
            raise ValueError("PLANTGUARD_PHOTO_SIGNING_KEY must be changed in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
