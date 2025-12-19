"""
Утилита для работы с курсами валют.
Обеспечивает получение курса USD/RUB с механизмом кэширования.
"""

import time
import logging
from httpx import AsyncClient

logger = logging.getLogger(__name__)

# Кэш для курса доллара
_usd_rate_cache = {
    "rate": 100.0,
    "last_update": 0
}
CACHE_TTL = 3600  # 1 час


async def get_usd_rate() -> float:
    """
    Возвращает текущий курс USD/RUB.
    Использует кэширование, чтобы избежать частых запросов к API.
    """
    now = time.time()
    
    # Возвращаем из кэша, если он еще свежий
    if now - _usd_rate_cache["last_update"] < CACHE_TTL:
        return _usd_rate_cache["rate"]

    try:
        async with AsyncClient(timeout=10.0) as client:
            res = await client.get("https://api.coinbase.com/v2/prices/USD-RUB/spot")
            if res.status_code == 200:
                rate = float(res.json().get("data", {}).get("amount", 100.0))
                _usd_rate_cache["rate"] = rate
                _usd_rate_cache["last_update"] = now
                logger.info(f"Обновлен курс USD/RUB: {rate}")
                return rate
            else:
                logger.warning(f"Не удалось получить курс валют, статус: {res.status_code}")
    except Exception as e:
        logger.error(f"Ошибка при получении курса USD: {e}")

    # В случае ошибки возвращаем последнее известное значение или дефолтное
    return _usd_rate_cache["rate"]
