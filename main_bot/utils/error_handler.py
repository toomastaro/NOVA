import logging
from functools import wraps
from typing import Callable

logger = logging.getLogger(__name__)


def safe_handler(stage_info: str):
    """
    Декоратор для оборачивания хендлеров в блок try-except с логированием ошибок.
    
    Args:
         stage_info: Короткое описание этапа/хендлера.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Ошибка в {stage_info}: {e}", exc_info=True)
                # Отправка отчета в Telegram отключена по запросу пользователя.
                pass

        return wrapper
    return decorator
