import os

from dotenv import load_dotenv

load_dotenv()



class Config:
    VERSION = "1.0.13"

    # Bot
    BOT_TOKEN = os.getenv('BOT_TOKEN')
    BACKUP_CHAT_ID = int(os.getenv('NOVA_BKP')) if os.getenv('NOVA_BKP') else 0
    ADMIN_SUPPORT = int(os.getenv("ADMIN_SUPPORT"))

    PG_USER = os.getenv('PG_USER')
    PG_PASS = os.getenv('PG_PASS')
    PG_HOST = os.getenv('PG_HOST')
    PG_DATABASE = os.getenv('PG_DATABASE')
    WEBHOOK_DOMAIN = os.getenv("WEBHOOK_DOMAIN")
    WEBHOOK_URL_BOT = os.getenv("WEBHOOK_URL_BOT")

    API_ID = int(os.getenv("API_ID"))
    API_HASH = os.getenv("API_HASH")

    # Payments
    CRYPTO_BOT_TOKEN = os.getenv('CRYPTO_BOT_TOKEN')

    ADMINS = [int(i) for i in os.getenv("ADMINS").split(",")]
    TARIFFS = {
        'subscribe': {
            0: {
                'name': '💫 30 дней — 149₽',
                'period': 30,
                'amount': 8
            },
            1: {
                'name': '✨ 90 дней — 399₽ (133₽/мес)',
                'period': 90,
                'amount': 399
            },
            2: {
                'name': '🌟 180 дней — 749₽ (124₽/мес)',
                'period': 180,
                'amount': 749
            },
            3: {
                'name': '⭐️ 365 дней — 1399₽ (116₽/мес)',
                'period': 365,
                'amount': 1399
            }
        }
    }
