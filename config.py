import os

from dotenv import load_dotenv

load_dotenv()



class Config:
    VERSION = "1.0.580"

    # Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    BOT_LINK = os.getenv('BOT_LINK', 'https://t.me/novatg')
    BACKUP_CHAT_ID = int(os.getenv('NOVA_BKP')) if os.getenv('NOVA_BKP') else 0
    ADMIN_SUPPORT = int(os.getenv("ADMIN_SUPPORT"))

    PG_USER = os.getenv('PG_USER')
    PG_PASS = os.getenv('PG_PASS')
    PG_HOST = os.getenv('PG_HOST')
    PG_DATABASE = os.getenv('PG_DATABASE')
    WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")
    WEBHOOK_URL_BOT = os.getenv("WEBHOOK_URL_BOT")

    # Database
    DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 30))
    DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 10))
    DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 40))
    DB_TIMEOUT_SECONDS = int(os.getenv("DB_TIMEOUT_SECONDS", 30))
    DB_MAX_RETRY_ATTEMPTS = int(os.getenv("DB_MAX_RETRY_ATTEMPTS", 3))

    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")
    
    # Scheduler
    zakup_timer = int(os.getenv("zakup_timer", 600))

    # Payments
    CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN')
    PLATEGA_MERCHANT = os.getenv('PLATEGA_MERCHANT')
    PLATEGA_SECRET = os.getenv('PLATEGA_SECRET')

    # Features
    ENABLE_AD_BUY_MODULE = os.getenv("ENABLE_AD_BUY_MODULE", "false").lower() == "true"

    ADMINS = [int(i) for i in os.getenv("ADMINS").split(",")]
    TARIFFS = {
        'subscribe': {
            0: {
                'name': '99₽ (2̶9̶9̶₽̶) за 30 дней',
                'period': 30,
                'amount': 99
            }
        }
    }

config = Config()
