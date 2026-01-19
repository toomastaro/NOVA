"""
Модуль настройки логирования.
"""

import logging
import sys


def setup_logging() -> None:
    """
    Настройка центральной конфигурации логирования.

    Устанавливает формат логов, обработчики (stdout) и уровней логирования
    для сторонних библиотек, чтобы уменьшить шум.
    """
    # Конфигурация корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    # Тихие логи для основных библиотек
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    
    # Оставляем тихими тяжелые и шумные библиотеки
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    logging.getLogger("main_bot.database").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Конфигурация логирования успешно настроена.")
