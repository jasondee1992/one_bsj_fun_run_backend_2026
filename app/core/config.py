from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "OneBSJ Fun Run API"
    environment: str = "local"
    database_url: str = "sqlite:///./data/onebsj_fun_run.db"
    frontend_origins: list[str] = Field(
        default_factory=lambda: ["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    admin_username: str = "admin"
    admin_password: str = "admin123"
    admin_token_secret: str = "change-this-local-secret"
    access_token_expire_minutes: int = 720

    bib_prefix: str = "OneBSJ"
    event_name: str = "OneBSJ Fun Run 2026"
    default_currency: str = "PHP"
    default_registration_amount: float = 0

    @field_validator("frontend_origins", mode="before")
    @classmethod
    def parse_frontend_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return value
        return ["http://localhost:3000", "http://127.0.0.1:3000"]

    @property
    def sqlite_file_path(self) -> Path | None:
        prefix = "sqlite:///"
        if not self.database_url.startswith(prefix):
            return None
        raw_path = self.database_url.removeprefix(prefix)
        if raw_path == ":memory:":
            return None
        return Path(raw_path)


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

