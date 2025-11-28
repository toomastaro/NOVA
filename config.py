from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration settings.
    Loads values from .env file and environment variables.
    """
    # App
    DEBUG: bool = False
    VERSION: str = "1.0.28"

    # Bot
    BOT_TOKEN: str
    ADMIN_SUPPORT: int

    # Database
    PG_USER: str
    PG_PASS: str
    PG_HOST: str
    PG_DATABASE: str

    # Webhook
    WEBHOOK_DOMAIN: str
    WEBHOOK_URL_BOT: str | None = None

    # API
    API_ID: int
    API_HASH: str

    # Payments
    CRYPTO_BOT_TOKEN: str | None = None

    # Admins
    ADMINS: list[int]

    # Backup channel
    NOVA_BKP: int

    @field_validator("ADMINS", mode="before")
    @classmethod
    def parse_admins(cls, v: Any) -> list[int]:
        if not v:
            return []
        if isinstance(v, str):
            return [int(x) for x in v.split(",") if x.strip()]
        if isinstance(v, list):
            return v
        raise ValueError("ADMINS must be a string or list")

    # Tariffs (Default value, can be overridden but usually static)
    TARIFFS: dict[str, dict[int, dict[str, Any]]] = {
        "subscribe": {
            0: {"name": "💫 30 дней — 149₽", "period": 30, "amount": 8},
            1: {"name": "✨ 90 дней — 399₽ (133₽/мес)", "period": 90, "amount": 399},
            2: {"name": "🌟 180 дней — 749₽ (124₽/мес)", "period": 180, "amount": 749},
            3: {
                "name": "⭐️ 365 дней — 1399₽ (116₽/мес)",
                "period": 365,
                "amount": 1399,
            },
        }
    }

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore", case_sensitive=True
    )

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql+asyncpg://{self.PG_USER}:{self.PG_PASS}@{self.PG_HOST}/{self.PG_DATABASE}"


settings = Settings()
Config = settings  # For backward compatibility if needed, but better to migrate
