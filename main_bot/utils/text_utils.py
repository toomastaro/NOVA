"""
Утилиты для обработки текста.

Содержит функции очистки HTML тегов, генерации защитных тегов и другой обработки текста.
"""
import re
from typing import Any

# Предкомпилированные regex паттерны для производительности
_HTML_TAGS_PATTERN = re.compile(r'<[^>]+>')

def clean_html_text(text: str | None) -> str:
    """
    Эффективно очищает текст от HTML тегов.
    Возвращает 'Медиа', если текст отсутствует или пуст после очистки.
    """
    if not text:
        return "Медиа"
    
    # Удаление HTML тегов
    clean_text = _HTML_TAGS_PATTERN.sub('', text)
    
    return clean_text.strip() or "Медиа"

def get_protect_tag(protect: Any) -> str:
    """
    Возвращает тег защиты на основе настроек объекта protect.
    
    Args:
        protect: Объект с атрибутами arab (bool) и china (bool)
        
    Returns:
        Строка тега ('all', 'arab', 'china', '')
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
