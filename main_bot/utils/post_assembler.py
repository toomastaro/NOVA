"""
Модуль для сборки финальной структуры поста (Payload).
Отвечает за генерацию HTML-текста и упаковку всех опций сообщения.
"""

import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)

class PostAssembler:
    """
    Класс для сборки объектов постов в унифицированном формате.
    """

    @staticmethod
    def assemble_message_options(
        html_text: str,
        media_value: Optional[str] = None,
        media_type: Optional[str] = None,
        is_invisible: bool = False,
        buttons: Optional[Any] = None,
        reaction: Optional[Any] = None,
    ) -> dict:
        """
        Собирает словарь message_options для хранения в БД.

        Аргументы:
            html_text (str): Основной текст поста в формате HTML.
            media_value (str): URL изображения/видео или file_id.
            media_type (str): Тип медиа ('photo', 'video', 'animation').
            is_invisible (bool): Используется ли метод Скрытая ссылка.
            buttons: Кнопки (в формате для aiogram или JSON).
            reaction: Настройки реакций.

        Возвращает:
            dict: Собранный словарь опций.
        """
        
        import re
        # Очищаем текст от старых невидимых тегов (защита от дублирования)
        # Ищем паттерн <a href="...">\u200b</a> в начале строки
        clean_html = re.sub(r'^<a href="[^"]+">\u200b</a>', '', html_text)
        
        final_html = clean_html
        
        # Если метод "Скрытая ссылка", добавляем невидимый символ со ссылкой в начало
        if is_invisible and media_value:
            # \u200b - невидимый пробел нулевой ширины
            invisible_tag = f'<a href="{media_value}">\u200b</a>'
            # Проверка: если вдруг регулярка выше пропустила или мы добавили его вручную ранее
            if invisible_tag not in final_html:
                final_html = f"{invisible_tag}{final_html}"

        options = {
            "html_text": final_html,
            "media_type": media_type,
            "media_value": media_value,
            "is_invisible": is_invisible,
            "buttons": buttons,
            "reaction": reaction
        }
        
        logger.debug(f"Пост собран: type={media_type}, invisible={is_invisible}, len={len(final_html)}")
        return options

    @staticmethod
    def get_text_from_options(options: dict) -> str:
        """Извлекает текст из сохраненного словаря опций."""
        return options.get("html_text", "")

    @staticmethod
    def get_media_from_options(options: dict) -> tuple:
        """Возвращает (media_value, media_type, is_invisible)."""
        return (
            options.get("media_value"),
            options.get("media_type"),
            options.get("is_invisible", False)
        )
