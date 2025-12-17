"""
Скрипт глобального рефакторинга роутеров.

Проходит по всем файлам в целевой директории и заменяет устаревшие
вызовы `hand_add` на `get_router`. Используется для миграции
кодовой базы.

Запуск:
    python refactor_routers_global.py
"""

import logging
import os

from main_bot.utils.logger import setup_logging

# Настройка логирования
setup_logging()
logger = logging.getLogger(__name__)

# Целевая директория проекта
TARGET_DIR = r"C:\NOVA\main_bot"


def refactor_files():
    """
    Выполняет рефакторинг файлов в TARGET_DIR.

    Сканирует .py файлы, ищет вхождения 'hand_add' и заменяет на 'get_router'.
    """
    logger.info(f"Запуск рефакторинга в {TARGET_DIR}...")
    count = 0
    for root, dirs, files in os.walk(TARGET_DIR):
        # Сканируем все директории
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        content = f.read()

                    if "hand_add" in content:
                        new_content = content.replace("hand_add", "get_router")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        logger.info(f"Обновлен: {file_path}")
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка обработки {file_path}: {e}")

    logger.info(f"Рефакторинг завершен. Обновлено файлов: {count}.")


if __name__ == "__main__":
    refactor_files()
