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

from aiogram import Bot, types
from hello_bot.database.db import Database
from instance_bot import bot
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.database.user_bot.model import UserBot
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.schemas import MessageOptionsHello
from main_bot.utils.file_utils import TEMP_DIR

logger = logging.getLogger(__name__)


async def delete_bot_posts(user_bot: UserBot, message_ids: list[dict]):
    """
    Удалить сообщения бота.
    
    Args:
        user_bot: Объект пользовательского бота
        message_ids: Список словарей с chat_id и message_id для удаления
    """
    async with BotManager(user_bot.token) as bot_manager:
        validate = await bot_manager.validate_token()
        if not validate:
            return
        status = await bot_manager.status()
        if not status:
            return

        for message in message_ids:
            try:
                await bot_manager.bot.delete_message(**message)
            except Exception as e:
                # Игнорируем ошибку "сообщение не найдено" - это нормально (пользователь мог удалить вручную)
                if "message to delete not found" not in str(e).lower():
                    logger.error(f"Ошибка при удалении сообщения бота: {e}", exc_info=True)


async def start_delete_bot_posts():
    """
    Периодическая задача: удаление сообщений ботов по расписанию.
    
    Проверяет все посты ботов с установленным временем удаления
    и удаляет сообщения, если время истекло.
    """
    bot_posts = await db.bot_post.get_bot_posts_for_clear_messages()

    for bot_post in bot_posts:
        if (bot_post.delete_time + bot_post.start_timestamp) > time.time():
            continue

        messages = bot_post.message_ids
        if not messages:
            continue

        for bot_id in list(messages.keys()):
            user_bot = await db.user_bot.get_bot_by_id(int(bot_id))
            if user_bot:
                asyncio.create_task(delete_bot_posts(user_bot, messages[bot_id]["message_ids"]))
        
        # Обновляем delete_time, чтобы не пытаться удалять снова и снова
        await db.bot_post.update_bot_post(
            post_id=bot_post.id,
            delete_time=None
        )


async def send_bot_messages(other_bot: Bot, bot_post: BotPost, users, filepath: Path | str | None):
    """
    Отправить сообщения через бота всем пользователям.
    
    Args:
        other_bot: Экземпляр бота для отправки
        bot_post: Объект поста для рассылки
        users: Список ID пользователей для отправки
        filepath: Путь к медиафайлу (если есть)
        
    Returns:
        Словарь с результатами отправки
    """
    message_options = MessageOptionsHello(**bot_post.message)
    file_input = types.FSInputFile(str(filepath)) if filepath else None

    # Определяем тип сообщения и соответствующую функцию отправки
    if message_options.text:
        cor = other_bot.send_message
    elif message_options.photo:
        cor = other_bot.send_photo
        message_options.photo = file_input
    elif message_options.video:
        cor = other_bot.send_video
        message_options.video = file_input
    else:
        cor = other_bot.send_animation
        message_options.animation = file_input

    options = message_options.model_dump()

    # Удаляем неиспользуемые поля (Telegram API строг к лишним полям)
    keys_to_remove = ["show_caption_above_media", "disable_web_page_preview", "has_spoiler"]
    for key in keys_to_remove:
        options.pop(key, None)

    # Удаляем взаимоисключающие поля медиа
    if message_options.text:
        for k in ["photo", "video", "animation", "caption"]: options.pop(k, None)
    elif message_options.photo:
        for k in ["video", "animation", "text"]: options.pop(k, None)
    elif message_options.video:
        for k in ["photo", "animation", "text"]: options.pop(k, None)
    else:  # animation
        for k in ["photo", "video", "text"]: options.pop(k, None)

    options['parse_mode'] = 'HTML'

    success = 0
    message_ids = []

    # Отправка сообщений всем пользователям
    for user in users:
        try:
            options["chat_id"] = user
            if bot_post.text_with_name:
                get_user = await other_bot.get_chat(user)
                added_text = f"{get_user.username or get_user.first_name}\n\n"

                if message_options.text:
                    options["text"] = added_text + message_options.text
                if message_options.caption:
                    options["caption"] = added_text + message_options.caption

            message = await cor(**options)
            message_ids.append({"message_id": message.message_id, "chat_id": user})
            success += 1
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения бота пользователю {user}: {e}", exc_info=True)

        await asyncio.sleep(0.25)

    logger.info(f"✅ Рассылка завершена для бота {other_bot.id}. Успешно: {success}, Всего: {len(message_ids)}")
    return {other_bot.id: {"success": success, "message_ids": message_ids}}


async def process_bot(user_bot: UserBot, bot_post: BotPost, users, filepath):
    """
    Обработать отправку через бота.
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
            filepath=filepath
        )


async def send_bot_post(bot_post: BotPost):
    """
    Отправить пост через ботов.
    """
    logger.info(f"🚀 Начинаем обработку рассылки BotPost ID: {bot_post.id}")
    users_count = 0
    semaphore = asyncio.Semaphore(5)

    async def process_semaphore(*args):
        """Обертка для ограничения параллельных запросов"""
        async with semaphore:
            return await process_bot(*args)

    message_options = MessageOptionsHello(**bot_post.message)
    attrs = ["photo", "video", "animation"]
    file_id = next(
        (getattr(message_options, attr).file_id for attr in attrs if getattr(message_options, attr)),
        None
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
            return # Прерываем, если файл не загружен

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
                 logger.info(f"⚠️ Настройки не найдены по Chat ID {channel.chat_id}, пробуем по DB ID {channel.id}")
                 channel_settings = await db.channel_bot_settings.get_channel_bot_setting(
                    chat_id=channel.id
                 )

             if channel_settings and channel_settings.bot_id:
                 unique_bot_ids.add(channel_settings.bot_id)
                 logger.info(f"✅ Для канала {channel.title} найден бот ID: {channel_settings.bot_id}")
             else:
                 logger.warning(f"⚠️ Для канала {channel.title} (ID: {channel.id}) настройки НЕ найдены.")
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
        linked_settings = await db.channel_bot_settings.get_all_channels_in_bot_id(bot_id)
        
        for setting in linked_settings:
            # setting.id - это Telegram Chat ID канала
            linked_channel = await db.channel.get_channel_by_chat_id(setting.id)
            
            if linked_channel and linked_channel.subscribe:
                # Проверяем срок действия подписки
                if linked_channel.subscribe > int(time.time()):
                    has_active_subscription = True
                    logger.info(f"✅ Для бота {bot_id} найдена активная подписка через канал {linked_channel.title}")
                    break
        
        if not has_active_subscription:
            logger.warning(f"⚠️ Бот {user_bot.title} (ID: {bot_id}) не имеет активных подписок. Рассылка отменена.")
            continue

        other_db = Database()
        other_db.schema = user_bot.schema

        # Получаем всех пользователей бота
        try:
            raw_users = await other_db.get_all_users()
            # Extract IDs if records are returned
            users = [u.id if hasattr(u, 'id') else u for u in raw_users]
            logger.info(f"👥 Найдено {len(users)} пользователей для бота {user_bot.title} (ID: {bot_id})")
            
            users_count += len(users)

            tasks.append(
                process_semaphore(user_bot, bot_post, users, filepath)
            )
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
        message_ids=message_ids or None
    )


async def send_bot_posts():
    """
    Периодическая задача: отправка постов через ботов.
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
            # чтобы рассылка одного поста не блокировала поиск новых?
            # В оригинале было asyncio.create_task и потом gather.
            # Если постов много, это ок.
            tasks.append(asyncio.create_task(send_bot_post(post)))

        await asyncio.gather(*tasks, return_exceptions=True)
    except Exception as e:
        logger.error(f"Ошибка в цикле рассылки ботов: {e}", exc_info=True)
