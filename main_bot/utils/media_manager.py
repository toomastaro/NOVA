"""
Модуль для управления медиафайлами и методом их доставки.
Реализует адаптивную логику: использование Telegram file_id для коротких постов
и локальное сохранение + URL для длинных постов (метод Скрытая ссылка).
"""

import logging
import os
import uuid
from typing import Optional, Union, Tuple

from aiogram import types
from config import Config
from instance_bot import bot

logger = logging.getLogger(__name__)

class MediaManager:
    """
    Класс-менеджер для обработки медиа в системе адаптивного постинга.
    """

    @staticmethod
    async def process_media_for_post(
        message: types.Message, 
        caption: str
    ) -> Tuple[Optional[str], bool]:
        """
        Определяет, нужно ли сохранять медиа локально, и возвращает путь/ID.

        Аргументы:
            message (types.Message): Сообщение с медиа.
            caption (str): Текст подписи (для расчета лимитов).

        Возвращает:
            Tuple[Optional[str], bool]: 
                - str: file_id или URL на локальный файл.
                - bool: True, если это локальный URL (нужна скрытая ссылка), иначе False.
        """
        caption_len = len(caption) if caption else 0
        
        # Если текст > 1024, нам ОБЯЗАТЕЛЬНО нужна скрытая ссылка и локальное хранение
        if caption_len > 1024:
            local_url = await MediaManager.save_to_local(message)
            if local_url:
                return local_url, True
            
            logger.warning("Не удалось сохранить медиа локально, откатываемся на file_id (будет обрезано)")
        
        # В остальных случаях используем file_id
        file_id = MediaManager.get_file_id(message)
        return file_id, False

    @staticmethod
    def get_file_id(message: types.Message) -> Optional[str]:
        """Извлекает file_id из сообщения в зависимости от типа медиа."""
        if message.photo:
            return message.photo[-1].file_id
        if message.video:
            return message.video.file_id
        if message.animation:
            return message.animation.file_id
        if message.audio:
            return message.audio.file_id
        if message.document:
            return message.document.file_id
        return None

    @staticmethod
    async def save_to_local(message: types.Message) -> Optional[str]:
        """
        Скачивает медиа из Telegram и сохраняет в публичную папку.
        Возвращает внешний URL.
        """
        try:
            # Определяем медиа-объект
            media_obj = None
            ext = ".jpg"
            
            if message.photo:
                media_obj = message.photo[-1]
                ext = ".jpg"
            elif message.video:
                media_obj = message.video
                ext = ".mp4"
            elif message.animation:
                media_obj = message.animation
                ext = ".mp4"
            
            if not media_obj:
                return None

            # Подготовка путей
            os.makedirs(Config.PUBLIC_IMAGES_PATH, exist_ok=True)
            unique_name = f"{uuid.uuid4().hex}{ext}"
            file_path = os.path.join(Config.PUBLIC_IMAGES_PATH, unique_name)

            # Скачивание
            await bot.download(media_obj, destination=file_path)
            
            # Формирование URL
            public_url = f"{Config.PUBLIC_IMAGES_URL}{unique_name}"
            
            logger.info(f"Медиа сохранено локально: {unique_name} -> {public_url}")
            return public_url

        except Exception as e:
            logger.error(f"Ошибка при локальном сохранении медиа: {e}", exc_info=True)
            return None
