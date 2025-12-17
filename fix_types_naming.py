"""
Скрипт переименования файла типов и обновления импортов.

Выполняет миграцию названия файла `types.py` -> `db_types.py` в пакете
`main_bot.database` и обновляет все соответствующие импорты в проекте.

Запуск:
    python fix_types_naming.py
"""

import logging
import os

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("FixTypesNaming")

PROJECT_ROOT = r"C:\NOVA"
OLD_FILE = os.path.join(PROJECT_ROOT, "main_bot", "database", "types.py")
NEW_FILE = os.path.join(PROJECT_ROOT, "main_bot", "database", "db_types.py")

SEARCH_STR = "from main_bot.database.types import"
REPLACE_STR = "from main_bot.database.db_types import"


def main():
    """
    Основная функция миграции.

    1. Переименовывает файл `types.py` в `db_types.py`.
    2. Сканирует все .py файлы проекта и обновляет строки импорта.
    """
    # 1. Переименование файла
    if os.path.exists(OLD_FILE):
        try:
            os.rename(OLD_FILE, NEW_FILE)
            logger.info(f"Переименован {OLD_FILE} -> {NEW_FILE}")
        except OSError as e:
            logger.error(f"Ошибка переименования файла: {e}")
            return
    elif os.path.exists(NEW_FILE):
        logger.info(f"Файл уже переименован в {NEW_FILE}")
    else:
        logger.warning(f"Ошибка: Исходный файл {OLD_FILE} не найден!")

    # 2. Обновление импортов
    count = 0
    for root, dirs, files in os.walk(PROJECT_ROOT):
        # Пропускаем служебные директории
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue

        for file in files:
            if file.endswith(".py") and file != "fix_types_naming.py":
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8") as f:
                        content = f.read()

                    if SEARCH_STR in content:
                        new_content = content.replace(SEARCH_STR, REPLACE_STR)
                        with open(filepath, "w", encoding="utf-8") as f:
                            f.write(new_content)
                        logger.info(f"Обновлены импорты в: {filepath}")
                        count += 1
                except Exception as e:
                    logger.error(f"Ошибка обработки {filepath}: {e}")

    logger.info(f"Завершено. Обновлено файлов: {count}.")


if __name__ == "__main__":
    main()
