"""
Утилиты для работы с текстом и форматированием.

Этот модуль содержит функции для:
- Обработки текста
- Форматирования данных
- Работы с тегами защиты
"""
import logging

from main_bot.utils.schemas import Protect

logger = logging.getLogger(__name__)


def get_protect_tag(protect: Protect) -> str:
    """
    Получить тег защиты на основе настроек.
    
    Args:
        protect: Объект с настройками защиты (arab, china)
        
    Returns:
        Строка с тегом защиты: "all", "arab", "china" или ""
    """
    if protect.arab and protect.china:
        protect_tag = "all"
    elif protect.arab:
        protect_tag = "arab"
    elif protect.china:
        protect_tag = "china"
    else:
        protect_tag = ""

    return protect_tag
