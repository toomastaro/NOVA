"""
Утилита для загрузки медиафайлов с длинными подписями через Premium-аккаунт.
Используется только для функционала постинга (Post), чтобы обойти лимит бота в 1024 символа.
"""

import logging
import os
import asyncio
from pathlib import Path
from typing import Optional, Union

from telethon import TelegramClient, types, utils
from aiogram import types as aiogram_types

from config import Config
from instance_bot import bot as main_bot
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)

class PremiumUploader:
    """
    Класс для загрузки медиа через Premium-сессию Telethon.
    """

    @staticmethod
    async def upload_media(
        chat_id: int,
        caption: str,
        media_file_id: Optional[str] = None,
        file_path: Optional[str] = None,
        is_video: bool = False,
        is_animation: bool = False
    ) -> Optional[int]:
        """
        Загружает медиа в указанный чат через Telethon.

        Args:
            chat_id: ID целевого чата (бэкап-канал).
            caption: Текст подписи (может быть > 1024 символов).
            media_file_id: file_id файла в Telegram (если нет локального пути).
            file_path: Локальный путь к файлу (если есть).
            is_video: Флаг видео-файла.
            is_animation: Флаг анимации (GIF).

        Returns:
            int: message_id созданного сообщения или None при ошибке.
        """
        session_path = Path(Config.PREMIUM_SESSION_PATH)
        
        if not session_path.exists():
            # Попытка поиска в других местах, если путь относительный
            alt_path = Path(os.getcwd()) / session_path
            if alt_path.exists():
                session_path = alt_path
            else:
                logger.error(f"Файл премиум-сессии не найден по пути: {session_path}")
                return None

        temp_path = None
        try:
            # 1. Если дан только file_id, скачиваем файл через основного бота
            if media_file_id and not file_path:
                logger.debug(f"Скачивание медиа {media_file_id} для Premium-загрузки...")
                file = await main_bot.get_file(media_file_id)
                temp_path = f"temp_premium_{media_file_id}_{Path(file.file_path).name}"
                await main_bot.download_file(file.file_path, temp_path)
                file_path = temp_path

            if not file_path or not os.path.exists(file_path):
                logger.error("Нет файла для загрузки через Premium-аккаунт")
                return None

            # 2. Инициализируем сессию через SessionManager (для потокобезопасности и блокировок)
            async with SessionManager(session_path) as manager:
                if not manager or not manager.client:
                    logger.error("Не удалось инициализировать Premium-клиента")
                    return None

                # Парсинг HTML-сущностей для Telethon
                # Telethon's utils.html.parse might not support <tg-spoiler>, replace with <spoiler>
                caption_for_parse = caption.replace('<tg-spoiler>', '<spoiler>').replace('</tg-spoiler>', '</spoiler>')
                text, entities = utils.html.parse(caption_for_parse)
                
                logger.info(f"Загрузка медиа ({len(caption)} симв.) в {chat_id} через Premium...")
                
                # Подготовка медиа-атрибутов
                attributes = []
                if is_video:
                    attributes.append(types.DocumentAttributeVideo(
                        duration=0, w=0, h=0, supports_streaming=True
                    ))
                elif is_animation:
                    attributes.append(types.DocumentAttributeAnimated())

                # Отправка файла
                sent_msg = await manager.client.send_file(
                    chat_id,
                    file_path,
                    caption=text,
                    formatting_entities=entities,
                    attributes=attributes,
                    force_document=False # Чтобы фото уходило как фото
                )
                
                if sent_msg:
                    logger.info(f"Медиа успешно загружено через Premium. Message ID: {sent_msg.id}")
                    return sent_msg.id
                
        except Exception as e:
            logger.error(f"Критическая ошибка Premium-загрузки: {e}", exc_info=True)
        finally:
            # Удаляем временный файл
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception as e:
                    logger.warning(f"Не удалось удалить временный файл {temp_path}: {e}")

        return None

    @staticmethod
    async def edit_caption(
        chat_id: int,
        message_id: int,
        caption: str
    ) -> bool:
        """
        Редактирует подпись сообщения через Telethon (Premium-аккаунт).

        Args:
            chat_id: ID целевого чата.
            message_id: ID сообщения для редактирования.
            caption: Новый текст подписи (может быть > 1024 символов).

        Returns:
            bool: True при успехе, False при ошибке.
        """
        session_path = Path(Config.PREMIUM_SESSION_PATH)
        
        if not session_path.exists():
            alt_path = Path(os.getcwd()) / session_path
            if alt_path.exists():
                session_path = alt_path
            else:
                logger.error(f"Файл премиум-сессии не найден для редактирования: {session_path}")
                return False

        try:
            async with SessionManager(session_path) as manager:
                if not manager or not manager.client:
                    logger.error("Не удалось инициализировать Premium-клиента для редактирования")
                    return False

                # Парсинг HTML для Telethon
                # Telethon's utils.html.parse might not support <tg-spoiler>, replace with <spoiler>
                caption_for_parse = caption.replace('<tg-spoiler>', '<spoiler>').replace('</tg-spoiler>', '</spoiler>')
                text, entities = utils.html.parse(caption_for_parse)
                
                logger.info(f"Редактирование подписи ({len(caption)} симв.) в {chat_id} (msg {message_id}) через Premium...")
                
                # Редактируем сообщение
                await manager.client.edit_message(
                    chat_id,
                    message_id,
                    text,
                    formatting_entities=entities
                )
                
                logger.info(f"Подпись успешно отредактирована через Premium в {chat_id} (msg {message_id})")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка редактирования подписи через Premium: {e}", exc_info=True)
            return False

