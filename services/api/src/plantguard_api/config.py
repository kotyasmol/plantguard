from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    environment: str = "development"
    cors_origins: str = "http://localhost:5173"
    max_image_bytes: int = 10 * 1024 * 1024

    model_config = SettingsConfigDict(env_prefix="PLANTGUARD_", env_file=".env")

    @property
    def allowed_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
