"""
Модуль конфигурации проекта.

Содержит класс Config, который загружает переменные окружения и
определяет основные константы для работы бота, базы данных, Redis
и других сервисов.

Используется во всем проекте для доступа к настройкам.
"""

import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """
    Класс конфигурации приложения.

    Хранит настройки бота, базы данных, Redis, платежных систем
    и другие параметры, загружаемые из переменных окружения.
    """

    VERSION = "1.0.988"

    # Настройки бота
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    BOT_LINK = os.getenv("BOT_LINK", "https://t.me/novatg")
    BOT_USERNAME = BOT_LINK.split("/")[-1] if BOT_LINK else "novatg"
    # ID чата для бэкапов. Если не задан - 0
    BACKUP_CHAT_ID = int(os.getenv("NOVA_BKP")) if os.getenv("NOVA_BKP") else 0
    ADMIN_SUPPORT = int(os.getenv("ADMIN_SUPPORT"))

    # Путь к Premium сессии для загрузки длинных постов
    PREMIUM_SESSION_PATH = os.path.join("main_bot", "utils", "sessions", "+37253850093.session")

    # Настройки базы данных (PostgreSQL)
    PG_USER = os.getenv("PG_USER")
    PG_PASS = os.getenv("PG_PASS")
    PG_HOST = os.getenv("PG_HOST")
    PG_DATABASE = os.getenv("PG_DATABASE")

    # Настройки Webhook
    WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")
    WEBHOOK_URL_BOT = os.getenv("WEBHOOK_URL_BOT")

    # Настройки Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_PASS = os.getenv("REDIS_PASSWORD")

    # Пул соединений базы данных
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 30))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 10))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 40))
    DB_TIMEOUT_SECONDS = int(os.getenv("DB_TIMEOUT_SECONDS", 30))
    DB_MAX_RETRY_ATTEMPTS = int(os.getenv("DB_MAX_RETRY_ATTEMPTS", 3))

    # Telegram API
    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")

    # Планировщик
    zakup_timer = int(os.getenv("zakup_timer", 600))

    # Платежные системы
    CRYPTO_BOT_TOKEN = os.getenv("CRYPTO_BOT_TOKEN")
    PLATEGA_MERCHANT = os.getenv("PLATEGA_MERCHANT")
    PLATEGA_SECRET = os.getenv("PLATEGA_SECRET")

    # Фичи
    ENABLE_AD_BUY_MODULE = os.getenv("ENABLE_AD_BUY_MODULE", "false").lower() == "true"
    TRIAL = os.getenv("TRIAL", "false").lower() == "true"
    TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", 3))

    # Лимиты
    NOVA_LIM = int(os.getenv("NOVA_LIM", 25))

    # Константы системы
    SOFT_DELETE_TIMESTAMP = 946684800  # 01.01.2000

    # Администраторы и тарифы
    ADMINS = [int(i) for i in os.getenv("ADMINS").split(",")]
    TARIFFS = {
        "subscribe": {0: {"name": "99₽ (2̶9̶9̶₽̶) за 30 дней", "period": 30, "amount": 99}}
    }


config = Config()
