"""
Планировщик задач для отправки сообщений через пользовательских ботов.

Этот модуль содержит функции для:
- Отправки рассылок через ботов
- Удаления сообщений ботов по расписанию
"""

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from aiogram import Bot, types
from aiogram.types import FSInputFile
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from hello_bot.database.db import Database
from instance_bot import bot
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.database.user_bot.model import UserBot
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.file_utils import TEMP_DIR
from main_bot.utils.schemas import MessageOptionsHello
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Боты: удаление сообщений (Background)")
async def delete_bot_posts(
    user_bot: UserBot, message_ids: List[Dict[str, Any]]
) -> None:
    """
    Удаляет отправленные сообщения через пользовательского бота.

    Параметры:
        user_bot (UserBot): Данные пользовательского бота.
        message_ids (List[Dict[str, Any]]): Список идентификаторов сообщений (chat_id, message_id).
    """
    async with BotManager(user_bot.token) as bot_manager:
        if not await bot_manager.validate_token():
            return
        if not await bot_manager.status():
            return

        for message in message_ids:
            try:
                await bot_manager.bot.delete_message(**message)
            except (TelegramForbiddenError, TelegramBadRequest) as e:
                # Ошибки прав или деактивации пользователя/бота — логируем предупреждение
                logger.warning(
                    f"Не удалось удалить сообщение бота в чате {message.get('chat_id')}: {e.message}"
                )
            except Exception as e:
                # Прочие ошибки: если сообщение не найдено — это нормально (удалено вручную)
                if "message to delete not found" not in str(e).lower():
                    logger.error(
                        f"Критическая ошибка при удалении сообщения бота: {e}", exc_info=True
                    )


@safe_handler("Боты: удаление сообщений (Background)", log_start=False)
async def start_delete_bot_posts() -> None:
    """
    Периодическая задача по очистке сообщений ботов с истекшим временем жизни.
    """
    bot_posts = await db.bot_post.get_bot_posts_for_clear_messages()

    for bot_post in bot_posts:
        # Проверка времени удаления (время старта + задержка удаления)
        if (bot_post.delete_time + bot_post.start_timestamp) > time.time():
            continue

        messages = bot_post.message_ids
        if not messages:
            continue

        # Запуск задач удаления для каждого задействованного бота
        for bot_id in list(messages.keys()):
            user_bot = await db.user_bot.get_bot_by_id(int(bot_id))
            if user_bot:
                asyncio.create_task(
                    delete_bot_posts(user_bot, messages[bot_id]["message_ids"])
                )

        # Помечаем пост как удаленный и очищаем список ID сообщений
        await db.bot_post.update_bot_post(
            post_id=bot_post.id, 
            deleted_at=int(time.time()), 
            status=Status.DELETED,
            message_ids=None
        )


async def send_bot_messages(
    other_bot: Bot,
    bot_post: BotPost,
    users: List[int],
    filepath: Optional[str],
    schema: str,
) -> Dict[int, Any]:
    """
    Отправить сообщения через бота всем пользователям.

    Аргументы:
        other_bot (Bot): Экземпляр бота для отправки.
        bot_post (BotPost): Объект поста для рассылки.
        users (List[int]): Список ID пользователей для отправки.
        filepath (Optional[str]): Путь к медиафайлу (если есть).

    Возвращает:
        Dict[int, Any]: Словарь с результатами отправки.
    """
    message_options = MessageOptionsHello(**bot_post.message)
    file_input = FSInputFile(str(filepath)) if filepath else None

    # Определяем тип сообщения и соответствующую функцию отправки
    if message_options.text:
        cor = other_bot.send_message
    elif message_options.photo:
        cor = other_bot.send_photo
    elif message_options.video:
        cor = other_bot.send_video
    else:
        cor = other_bot.send_animation

    options = message_options.model_dump()

    # Внедряем файл после дампа, чтобы избежать варнингов Pydantic при сериализации
    if file_input:
        if message_options.photo:
            options["photo"] = file_input
        elif message_options.video:
            options["video"] = file_input
        elif message_options.animation:
            options["animation"] = file_input

    # Обработка предпросмотра ссылок (disable_web_page_preview)
    if message_options.disable_web_page_preview:
        if message_options.text:
            options["link_preview_options"] = types.LinkPreviewOptions(is_disabled=True)
            
    # Удаляем неиспользуемые поля (Telegram API строг к лишним полям)
    keys_to_remove = [
        "show_caption_above_media",
        "disable_web_page_preview",
        "has_spoiler",
        "is_invisible",
        "media_type",
        "media_value",
        "html_text",
        "buttons",
        "reaction",
    ]
    for key in keys_to_remove:
        options.pop(key, None)

    # Удаляем взаимоисключающие поля медиа
    if message_options.text:
        for k in ["photo", "video", "animation", "caption"]:
            options.pop(k, None)
    elif message_options.photo:
        for k in ["video", "animation", "text"]:
            options.pop(k, None)
    elif message_options.video:
        for k in ["photo", "animation", "text"]:
            options.pop(k, None)
    else:  # animation
        for k in ["photo", "video", "text"]:
            options.pop(k, None)

    options["parse_mode"] = "HTML"

    success = 0
    message_ids = []

    # Отправка сообщений всем пользователям
    for user in users:
        try:
            options["chat_id"] = user
            name_placeholders = ["{{name}}", "{name}"]
            has_placeholder = any(
                (message_options.text and p in message_options.text) or 
                (message_options.caption and p in message_options.caption)
                for p in name_placeholders
            )

            if bot_post.text_with_name or has_placeholder:
                try:
                    get_user = await other_bot.get_chat(user)
                    name_part = (
                        get_user.first_name or get_user.username or "Пользователь"
                    )
                except Exception:
                    name_part = "Пользователь"

                if message_options.text:
                    text_content = message_options.text
                    for p in name_placeholders:
                        text_content = text_content.replace(p, name_part)
                    
                    if bot_post.text_with_name and not any(p in message_options.text for p in name_placeholders):
                        options["text"] = f"{name_part}!\n\n{text_content}"
                    else:
                        options["text"] = text_content

                if message_options.caption:
                    caption_content = message_options.caption
                    for p in name_placeholders:
                        caption_content = caption_content.replace(p, name_part)
                        
                    if bot_post.text_with_name and not any(p in message_options.caption for p in name_placeholders):
                        options["caption"] = f"{name_part}!\n\n{caption_content}"
                    else:
                        options["caption"] = caption_content

            message = await cor(**options)
            message_ids.append({"message_id": message.message_id, "chat_id": user})
            success += 1
        except (TelegramForbiddenError, TelegramBadRequest) as e:
            logger.warning(
                f"Пользователь {user} деактивирован (Бот: {other_bot.id}): {e.message}"
            )
            try:
                other_db = Database()
                other_db.schema = schema
                await other_db.update_user(user_id=user, is_active=False)
            except Exception as db_err:
                logger.error(f"Ошибка БД при деактивации юзера {user}: {db_err}")
        except Exception as e:
            logger.error(
                f"Ошибка при отправке сообщения бота пользователю {user}: {e}",
                exc_info=True,
            )

        await asyncio.sleep(0.06)

    logger.info(
        f"✅ Рассылка завершена для бота {other_bot.id}. Успешно: {success}, Всего: {len(message_ids)}"
    )
    return {other_bot.id: {"success": success, "message_ids": message_ids}}


async def process_bot(
    user_bot: UserBot, bot_post: BotPost, users: List[int], filepath: Optional[str]
) -> Dict[int, Any]:
    """
    Обработать отправку через API бота.

    Проверяет токен и статус, затем отправляет сообщения.

    Аргументы:
        user_bot (UserBot): Объект бота.
        bot_post (BotPost): Пост.
        users (List[int]): Пользователи.
        filepath (Optional[str]): Медиафайл.

    Возвращает:
        Dict[int, Any]: Результат отправки.
    """
    async with BotManager(user_bot.token) as bot_manager:
        validate = await bot_manager.validate_token()

        if not validate:
            raise Exception("TOKEN_INVALID")
        status = await bot_manager.status()
        if not status:
            raise Exception("STATUS_INVALID")

        return await send_bot_messages(
            other_bot=bot_manager.bot,
            bot_post=bot_post,
            users=users,
            filepath=filepath,
            schema=user_bot.schema,
        )


@safe_handler("Боты: отправка поста (Background)")
async def send_bot_post(bot_post: BotPost) -> None:
    """
    Отправить пост через ботов (Основная логика).

    1. Загружает файл (если есть).
    2. Определяет ботов, через которые нужно слать (на основе каналов в настройках).
    3. Проверяет подписки каналов.
    4. Собирает пользователей каждого бота.
    5. Запускает рассылку параллельно (с семафором).
    6. Обновляет статус поста.

    Аргументы:
        bot_post (BotPost): Пост для отправки.
    """
    logger.info(f"🚀 Начинаем обработку рассылки BotPost ID: {bot_post.id}")
    
    # Сразу «застолбим» пост, чтобы планировщик не взял его повторно (защита от дубликатов)
    await db.bot_post.update_bot_post(post_id=bot_post.id, status=Status.FINISH)
    
    users_count = 0
    semaphore = asyncio.Semaphore(5)

    async def process_semaphore(*args):
        """Обертка для ограничения параллельных запросов"""
        async with semaphore:
            return await process_bot(*args)

    message_options = MessageOptionsHello(**bot_post.message)
    attrs = ["photo", "video", "animation"]
    file_id = next(
        (
            getattr(message_options, attr).file_id
            for attr in attrs
            if getattr(message_options, attr)
        ),
        None,
    )

    filepath = None
    if file_id:
        try:
            get_file = await bot.get_file(file_id)
            # Используем TEMP_DIR
            filename = f"mail_{Path(get_file.file_path).name}"
            filepath = TEMP_DIR / filename
            await bot.download(file_id, str(filepath))
        except Exception as e:
            logger.error(f"Ошибка загрузки файла для рассылки: {e}")
            return  # Прерываем, если файл не загружен

    tasks = []

    # 2. Подготовка задач для каждого канала
    unique_bot_ids = set()

    # Сначала определяем уникальных ботов из выбранных каналов
    for chat_id in bot_post.chat_ids:
        try:
            # ВАЖНО: chat_ids здесь это именно ID каналов (Telegram ID), как выбрал юзер.
            # Но настройки (ChannelBotSetting) привязаны к ID канала в базе данных (PK), а не к Telegram ID.

            # 1. Находим канал по Telegram ID
            channel = await db.channel.get_channel_by_chat_id(int(chat_id))
            if not channel:
                logger.warning(f"⚠️ Канал с ID {chat_id} не найден в базе данных.")
                continue

            # 2. Пробуем найти настройки по Telegram Chat ID
            channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
                chat_id=channel.chat_id
            )

            if not channel_settings:
                # Если не нашли, пробуем по Database ID (PK)
                logger.info(
                    f"⚠️ Настройки не найдены по Chat ID {channel.chat_id}, пробуем по DB ID {channel.id}"
                )
                channel_settings = (
                    await db.channel_bot_settings.get_channel_bot_setting(
                        chat_id=channel.id
                    )
                )

            if channel_settings and channel_settings.bot_id:
                unique_bot_ids.add(channel_settings.bot_id)
                logger.info(
                    f"✅ Для канала {channel.title} найден бот ID: {channel_settings.bot_id}"
                )
            else:
                logger.warning(
                    f"⚠️ Для канала {channel.title} (ID: {channel.id}) настройки НЕ найдены."
                )
        except Exception as e:
            logger.error(f"❌ Ошибка при разрешении бота для канала {chat_id}: {e}")
            continue

    # 3. Итерируем по уникальным ботам
    for bot_id in unique_bot_ids:
        user_bot = await db.user_bot.get_bot_by_id(int(bot_id))

        if not user_bot:
            logger.warning(f"⚠️ Бот с ID {bot_id} не найден в базе данных.")
            continue

        # Проверка подписки: разрешаем, если ХОТЯ БЫ ОДИН канал, привязанный к боту, имеет активную подписку
        has_active_subscription = False

        # Получаем все настройки (связки канал-бот) для этого бота
        linked_settings = await db.channel_bot_settings.get_all_channels_in_bot_id(
            bot_id
        )

        for setting in linked_settings:
            # setting.id - это Telegram Chat ID канала
            linked_channel = await db.channel.get_channel_by_chat_id(setting.id)

            if linked_channel and linked_channel.subscribe:
                # Проверяем срок действия подписки
                if linked_channel.subscribe > int(time.time()):
                    has_active_subscription = True
                    logger.info(
                        f"✅ Для бота {bot_id} найдена активная подписка через канал {linked_channel.title}"
                    )
                    break

        if not has_active_subscription:
            logger.warning(
                f"⚠️ Бот {user_bot.title} (ID: {bot_id}) не имеет активных подписок. Рассылка отменена."
            )
            continue

        other_db = Database()
        other_db.schema = user_bot.schema

        # Получаем всех пользователей бота
        try:
            raw_users = await other_db.get_all_users()
            # Извлекаем ID, если возвращаются записи
            users = [u.id if hasattr(u, "id") else u for u in raw_users]
            logger.info(
                f"👥 Найдено {len(users)} пользователей для бота {user_bot.title} (ID: {bot_id})"
            )

            users_count += len(users)

            tasks.append(process_semaphore(user_bot, bot_post, users, filepath))
        except Exception as e:
            logger.error(f"Ошибка получения пользователей для бота {bot_id}: {e}")
            continue

    success_count = 0
    message_ids = {}

    start_timestamp = int(time.time())

    # Выполнение всех задач
    if tasks:
        result = await asyncio.gather(*tasks, return_exceptions=True)
        for i in result:
            if not isinstance(i, dict):
                continue
            # Собираем статистику отправленных сообщений
            for bot_id, res in i.items():
                success_count += res["success"]
                if bot_id not in message_ids:
                    message_ids[bot_id] = {}
                message_ids[bot_id]["message_ids"] = res["message_ids"]

    # Удаление временного файла
    if filepath:
        try:
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Ошибка при удалении файла {filepath}: {e}", exc_info=True)

    end_timestamp = int(time.time())

    # Обновление статуса поста
    await db.bot_post.update_bot_post(
        post_id=bot_post.id,
        success_send=success_count,
        error_send=users_count - success_count,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        status=Status.FINISH,
        message_ids=message_ids or None,
    )


@safe_handler("Боты: отправка постов (Background)", log_start=False)
async def send_bot_posts() -> None:
    """
    Периодическая задача: отправка постов через ботов.

    Ищет посты со статусом 'wait' (или готов к отправке) и запускает их обработку.
    """
    try:
        posts = await db.bot_post.get_bot_post_for_send()
        if posts:
            logger.info(f"🔎 Найдено {len(posts)} постов для рассылки.")
        if not posts:
            return

        tasks = []
        for post in posts:
            # Создаем таск и не ждем его завершения здесь,
            # чтобы рассылка одного поста не блокировала поиск новых
            tasks.append(asyncio.create_task(send_bot_post(post)))

        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Ошибка в цикле рассылки ботов: {e}", exc_info=True)
