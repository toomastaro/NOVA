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
    def _convert_buttons(reply_markup: Optional[Union[aiogram_types.InlineKeyboardMarkup, aiogram_types.ReplyKeyboardMarkup]]) -> Optional[list]:
        """
        Конвертирует кнопки из формата aiogram в формат Telethon.
        ВАЖНО: User-аккаунт через Telethon может отправлять только URL-кнопки.
        Callback-кнопки будут проигнорированы или пропущены.
        """
        if not reply_markup or not isinstance(reply_markup, aiogram_types.InlineKeyboardMarkup):
            return None
        
        from telethon import Button
        
        telethon_rows = []
        for row in reply_markup.inline_keyboard:
            telethon_row = []
            for btn in row:
                if btn.url:
                    telethon_row.append(Button.url(btn.text, btn.url))
                # Callback кнопки нельзя отправить от имени обычного пользователя (не бота)
            if telethon_row:
                telethon_rows.append(telethon_row)
        
        return telethon_rows if telethon_rows else None

    @staticmethod
    async def upload_media(
        chat_id: int,
        caption: str,
        media_file_id: Optional[str] = None,
        file_path: Optional[str] = None,
        is_video: bool = False,
        is_animation: bool = False,
        reply_markup: Optional[aiogram_types.InlineKeyboardMarkup] = None
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

                # Парсинг HTML для Telethon с поддержкой спойлеров
                # Трюк: заменяем спойлеры на уникальные ссылки, которые Telethon понимает, 
                # а затем конвертируем их в сущности спойлера.
                spoiler_url = "spoiler://"
                marked_caption = caption.replace('<tg-spoiler>', f'<a href="{spoiler_url}">').replace('</tg-spoiler>', '</a>')
                
                logger.info("PremiumUploader: парсинг HTML (длина %d) с подменой спойлеров на URL", len(caption))
                text, entities = utils.html.parse(marked_caption)
                
                final_entities = []
                for e in entities:
                    # Если это наша временная ссылка - превращаем в спойлер
                    if isinstance(e, types.MessageEntityTextUrl) and e.url == spoiler_url:
                        final_entities.append(types.MessageEntitySpoiler(offset=e.offset, length=e.length))
                    else:
                        final_entities.append(e)
                
                entities = final_entities

                # Вывод типов сущностей для контроля
                entity_types = [type(e).__name__ for e in entities]
                logger.info(
                    "PremiumUploader: парсинг завершен. Текст: %d симв, сущностей: %d. Типы: %s",
                    len(text),
                    len(entities),
                    ", ".join(set(entity_types)) if entity_types else "none"
                )
                
                logger.info(f"Загрузка медиа ({len(caption)} симв.) в {chat_id} через Premium...")
                
                # Подготовка медиа-атрибутов
                attributes = []
                if is_video:
                    attributes.append(types.DocumentAttributeVideo(
                        duration=0, w=0, h=0, supports_streaming=True
                    ))
                elif is_animation:
                    attributes.append(types.DocumentAttributeAnimated())

                # Проверка наличия спойлеров в сущностях
                has_spoiler_telet = any(isinstance(e, types.MessageEntitySpoiler) for e in entities)
                logger.info("PremiumUploader: финальная проверка перед отправкой. Найдено спойлеров: %s", has_spoiler_telet)

                # Отправка файла
                sent_msg = await manager.client.send_file(
                    chat_id,
                    file_path,
                    caption=text,
                    formatting_entities=entities,
                    attributes=attributes,
                    buttons=PremiumUploader._convert_buttons(reply_markup),
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
        caption: str,
        reply_markup: Optional[aiogram_types.InlineKeyboardMarkup] = None
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

                # Парсинг HTML для Telethon с поддержкой спойлеров
                spoiler_url = "spoiler://"
                marked_caption = caption.replace('<tg-spoiler>', f'<a href="{spoiler_url}">').replace('</tg-spoiler>', '</a>')
                
                logger.info("PremiumUploader (Edit): парсинг HTML (длина %d) с подменой спойлеров на URL", len(caption))
                text, entities = utils.html.parse(marked_caption)
                
                final_entities = []
                for e in entities:
                    if isinstance(e, types.MessageEntityTextUrl) and e.url == spoiler_url:
                        final_entities.append(types.MessageEntitySpoiler(offset=e.offset, length=e.length))
                    else:
                        final_entities.append(e)
                
                entities = final_entities
                
                # Вывод всех типов сущностей для отладки
                entity_types = [type(e).__name__ for e in entities]
                logger.info(
                    "PremiumUploader (Edit): парсинг завершен. Текст: %d симв, сущностей: %d. Типы: %s",
                    len(text),
                    len(entities),
                    ", ".join(set(entity_types)) if entity_types else "none"
                )
                
                # Редактируем сообщение
                await manager.client.edit_message(
                    chat_id,
                    message_id,
                    text,
                    formatting_entities=entities,
                    buttons=PremiumUploader._convert_buttons(reply_markup)
                )
                
                logger.info(f"Подпись успешно отредактирована через Premium в {chat_id} (msg {message_id})")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка редактирования подписи через Premium: {e}", exc_info=True)
            return False

    @staticmethod
    async def edit_media(
        chat_id: int,
        message_id: int,
        caption: str,
        media_file_id: Optional[str] = None,
        file_path: Optional[str] = None,
        is_video: bool = False,
        is_animation: bool = False,
        reply_markup: Optional[aiogram_types.InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Редактирует медиа и подпись сообщения через Telethon (Premium-аккаунт).

        Args:
            chat_id: ID целевого чата.
            message_id: ID сообщения для редактирования.
            caption: Новый текст подписи.
            media_file_id: file_id нового файла.
            file_path: Локальный путь к новому файлу.
            is_video: Флаг видео.
            is_animation: Флаг анимации.

        Returns:
            bool: True при успехе, False при ошибке.
        """
        session_path = Path(Config.PREMIUM_SESSION_PATH)
        if not session_path.exists():
            return False

        temp_path = None
        try:
            # 1. Скачиваем новый файл если нужно
            if media_file_id and not file_path:
                file = await main_bot.get_file(media_file_id)
                temp_path = f"temp_edit_{media_file_id}_{Path(file.file_path).name}"
                await main_bot.download_file(file.file_path, temp_path)
                file_path = temp_path

            if not file_path or not os.path.exists(file_path):
                logger.error("Нет файла для редактирования медиа через Premium")
                return False

            async with SessionManager(session_path) as manager:
                if not manager or not manager.client:
                    return False

                # Парсинг HTML для Telethon
                spoiler_url = "spoiler://"
                marked_caption = caption.replace('<tg-spoiler>', f'<a href="{spoiler_url}">').replace('</tg-spoiler>', '</a>')
                text, entities = utils.html.parse(marked_caption)
                
                final_entities = []
                for e in entities:
                    if isinstance(e, types.MessageEntityTextUrl) and e.url == spoiler_url:
                        final_entities.append(types.MessageEntitySpoiler(offset=e.offset, length=e.length))
                    else:
                        final_entities.append(e)
                
                entities = final_entities

                # Подготовка атрибутов
                attributes = []
                if is_video:
                    attributes.append(types.DocumentAttributeVideo(duration=0, w=0, h=0, supports_streaming=True))
                elif is_animation:
                    attributes.append(types.DocumentAttributeAnimated())

                # Редактируем сообщение (заменяем медиа)
                await manager.client.edit_message(
                    chat_id,
                    message_id,
                    text,
                    file=file_path,
                    formatting_entities=entities,
                    attributes=attributes,
                    buttons=PremiumUploader._convert_buttons(reply_markup),
                    force_document=False
                )
                
                logger.info(f"Медиа и подпись успешно изменены через Premium в {chat_id} (msg {message_id})")
                return True
                
        except Exception as e:
            logger.error(f"Ошибка редактирования медиа через Premium: {e}", exc_info=True)
            return False
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except Exception:
                    pass

