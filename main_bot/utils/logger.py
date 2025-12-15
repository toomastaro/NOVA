import logging
import sys

def setup_logging():
    """
    Настройка центральной конфигурации логирования.
    """
    # Конфигурация корневого логгера
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

    # Установка уровней для сторонних библиотек, чтобы уменьшить шум
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)
    # Понижаем уровень логов для CRUD опубликованных постов
    logging.getLogger("main_bot.database.published_post.crud").setLevel(logging.WARNING)

    logger = logging.getLogger(__name__)
    logger.info("Конфигурация логирования успешно настроена.")
