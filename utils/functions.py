"""
Утилитарные функции общего назначения.

Содержит функции для работы с изображениями и стикерами (создание эмодзи).
"""

import logging


logger = logging.getLogger(__name__)


async def create_emoji(user_id: int, photo_bytes=None) -> str:
    """
    Создает кастомный эмодзи из фото пользователя (ОТКЛЮЧЕНО).
    """
    return "5393222813345663485"
