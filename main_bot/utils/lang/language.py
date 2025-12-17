import json
import logging
import pathlib

logger = logging.getLogger(__name__)

# Определяем путь к директории с языковыми файлами относительно текущего файла
CURRENT_DIR = pathlib.Path(__file__).parent.resolve()
RU_JSON_PATH = CURRENT_DIR / 'ru.json'

try:
    with open(RU_JSON_PATH, 'r', encoding='utf-8') as r_f:
        ru_text = json.load(r_f)
except FileNotFoundError:
    logger.critical(f"Файл локализации не найден: {RU_JSON_PATH}")
    ru_text = {}
except json.JSONDecodeError as e:
    logger.critical(f"Ошибка парсинга файла локализации {RU_JSON_PATH}: {e}")
    ru_text = {}
except Exception as e:
    logger.critical(f"Неизвестная ошибка при загрузке локализации: {e}", exc_info=True)
    ru_text = {}


languages = {
    'RU': ru_text,
}


def text(key: str, user_lang: str = 'RU') -> str | dict:
    """
    Получить текст по ключу.
    Если ключ не найден, возвращает сам ключ.
    """
    lang_data = languages.get(user_lang, languages['RU'])
    return lang_data.get(key, key)
