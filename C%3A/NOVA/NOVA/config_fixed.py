from typing import Any, Union

from pydantic import field_validator, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Настройки приложения.
    Загружает значения из .env файла и переменных окружения.
    """
    # Основные настройки приложения
    DEBUG: bool = False
    VERSION: str = "1.0.0"

    # Настройки Telegram бота
    BOT_TOKEN: str
    ADMIN_SUPPORT: int

    # Настройки базы данных PostgreSQL
    PG_USER: str
    PG_PASS: str
    PG_HOST: str
    PG_DATABASE: str

    # Настройки webhook'ов
    WEBHOOK_DOMAIN: str
    WEBHOOK_URL_BOT: str | None = None

    # API настройки для Telegram клиента
    API_ID: int
    API_HASH: str

    # Настройки платежных систем
    CRYPTO_BOT_TOKEN: str | None = None
    CRYPTO_BOT_API_TOKEN: str | None = None

    # Администраторы (список ID пользователей Telegram)
    ADMINS: list[int]
    
    # Дополнительные API ключи
    BEST_EXCHANGE_API: str | None = None
    TGSTAT_API: str | None = None
    
    # Таймеры (в секундах)
    RUBUSDTTIMER: int = 900  # таймер обновления курсов валют

    @field_validator("ADMINS", mode="before")
    @classmethod
    def parse_admins(cls, v: Any) -> list[int]:
        """
        Парсит администраторов из строки вида "123,456,789" в список [123, 456, 789]
        Поддерживает как строки, так и уже готовые списки.
        """
        if isinstance(v, str):
            try:
                # Убираем пробелы и разделяем по запятым
                admin_ids = []
                for admin_id in v.split(","):
                    clean_id = admin_id.strip()
                    if clean_id:  # проверяем что ID не пустой
                        admin_ids.append(int(clean_id))
                return admin_ids
            except ValueError as e:
                raise ValidationError(f"Ошибка парсинга ADMINS: {v}. Проверьте формат (должно быть: 123,456,789)") from e
        elif isinstance(v, list):
            # Если уже список, проверяем что все элементы - целые числа
            return [int(x) for x in v]
        else:
            raise ValidationError(f"ADMINS должен быть строкой или списком, получен: {type(v)}")

    # Тарифные планы (по умолчанию, можно переопределить)
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
        env_file=".env",
        env_file_encoding="utf-8", 
        extra="ignore",  # игнорируем лишние поля в .env
        case_sensitive=True  # учитываем регистр названий переменных
    )

    @property
    def DATABASE_URL(self) -> str:
        """
        Формирует URL подключения к базе данных PostgreSQL
        """
        return f"postgresql+asyncpg://{self.PG_USER}:{self.PG_PASS}@{self.PG_HOST}/{self.PG_DATABASE}"


# Создаем глобальный объект настроек
settings = Settings()

# Для обратной совместимости (лучше мигрировать на settings)
Config = settings