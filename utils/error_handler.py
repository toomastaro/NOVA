"""
Модуль обработки ошибок (декораторы).
"""

import logging
from functools import wraps
from typing import Any, Callable

# Настройка логгера
logger = logging.getLogger(__name__)


def safe_handler(stage_info: str, log_start: bool = True) -> Callable:
    """
    Декоратор для оборачивания хендлеров в блок try-except с логированием ошибок.
    Обеспечивает безопасное выполнение и стандартизированное логирование на русском языке.

    Аргументы:
         stage_info (str): Название сценария и действия на русском.
                           Формат: "Сценарий: действие — этап"
         log_start (bool): Логировать ли начало выполнения этапа. (default: True)

    Возвращает:
        Callable: Обернутая функция.
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Логируем начало выполнения этапа, если включено
            if log_start:
                logger.info(f"Старт этапа: {stage_info}")
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Логируем ошибку с трейсбэком
                logger.error(f"Ошибка в {stage_info}: {e}", exc_info=True)
                # Исключение подавляется, чтобы не поломать внешний поток (Telegram, API и т.д.)
                # Если требуется прерывание транзакции, логика должна быть обработана внутри функции.
                # Для критичных задач (API) может потребоваться возврат специфичного объекта ошибки,
                # но текущая реализация сохраняет поведение "не падать".
                pass

        return wrapper

    return decorator
