"""
Модуль для управления списком последних выбранных временных меток пользователей.
Использует Redis для хранения истории (до 3 последних значений).
"""

import logging
from main_bot.utils.redis_client import redis_client

logger = logging.getLogger(__name__)

RECENT_TIMES_KEY = "recent_times:{}"


async def get_recent_times(user_id: int) -> list[str]:
    """
    Получает список 3 последних выбранных временных меток пользователя.

    Args:
        user_id: ID пользователя Telegram.

    Returns:
        Список строк в формате "HH:MM".
    """
    if not redis_client:
        return []

    try:
        # Получаем все элементы списка
        times = await redis_client.lrange(RECENT_TIMES_KEY.format(user_id), 0, 2)
        return [t.decode() for t in times]
    except Exception as e:
        logger.error(f"Ошибка при получении последних времен из Redis для {user_id}: {e}")
        return []


async def save_recent_time(user_id: int, time_str: str):
    """
    Сохраняет выбранное время в список последних времен пользователя.
    Поддерживает только 3 последних уникальных значения.

    Args:
        user_id: ID пользователя Telegram.
        time_str: Строка времени в формате "HH:MM".
    """
    if not redis_client:
        return

    try:
        key = RECENT_TIMES_KEY.format(user_id)
        
        # Удаляем существующее такое же значение, чтобы переместить его в начало
        await redis_client.lrem(key, 0, time_str)
        
        # Добавляем в начало списка
        await redis_client.lpush(key, time_str)
        
        # Ограничиваем список 3 элементами
        await redis_client.ltrim(key, 0, 2)
    except Exception as e:
        logger.error(f"Ошибка при сохранении времени в Redis для {user_id}: {e}")
