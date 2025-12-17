"""
Модуль обработки ошибок (декораторы).
"""

import logging
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


def safe_handler(stage_info: str) -> Callable:
    """
    Декоратор для оборачивания хендлеров в блок try-except с логированием ошибок.

    Аргументы:
         stage_info (str): Короткое описание этапа/хендлера для логов.

    Возвращает:
        Callable: Обернутая функция.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Ошибка в {stage_info}: {e}", exc_info=True)
                # Отправка отчета в Telegram отключена по запросу пользователя.
                pass

        return wrapper
    return decorator
