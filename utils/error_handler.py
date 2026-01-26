"""
Модуль обработки ошибок (декораторы).
"""

import logging
import html
from functools import wraps
from typing import Any, Callable

# Настройка логгера
logger = logging.getLogger(__name__)


def safe_handler(stage_info: str, log_start: bool = False) -> Callable:
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
            from config import Config
            from instance_bot import bot

            # Логируем начало выполнения этапа, если включено
            if log_start:
                logger.info(f"Старт этапа: {stage_info}")
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                # Логируем ошибку с трейсбэком
                logger.error(f"Ошибка в {stage_info}: {e}", exc_info=True)

                # Отправка алерта в канал поддержки
                try:
                    if Config.ADMIN_SUPPORT:
                        error_type = type(e).__name__
                        alert_text = (
                            f"🚨 <b>Ошибка в NOVA</b>\n\n"
                            f"<b>📍 Этап:</b> {stage_info}\n"
                            f"<b>⚠️ Тип:</b> {error_type}\n"
                            f"<b>💬 Сообщение:</b> <code>{html.escape(str(e))}</code>\n\n"
                            f"<i>Проверьте логи сервера для деталей.</i>"
                        )
                        await bot.send_message(
                            chat_id=Config.ADMIN_SUPPORT,
                            text=alert_text,
                            parse_mode="HTML",
                        )
                except Exception as alert_err:
                    logger.error(f"Не удалось отправить алерт в поддержку: {alert_err}")

                # Исключение подавляется, чтобы не поломать внешний поток
                return None

        return wrapper

    return decorator
