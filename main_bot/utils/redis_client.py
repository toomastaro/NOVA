from redis.asyncio import Redis
from config import Config

# Инициализация Redis клиента
redis_client = Redis(
    host=Config.REDIS_HOST,
    port=Config.REDIS_PORT,
    password=Config.REDIS_PASS,
)
