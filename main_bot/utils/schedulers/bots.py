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

from aiogram import Bot, types
from hello_bot.database.db import Database
from instance_bot import bot
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.types import Status
from main_bot.database.user_bot.model import UserBot
from main_bot.utils.bot_manager import BotManager
from main_bot.utils.schemas import MessageOptionsHello

logger = logging.getLogger(__name__)


async def delete_bot_posts(user_bot: UserBot, message_ids: list[dict]):
    """Удалить сообщения бота"""
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
                logger.error(f"Error deleting bot message: {e}", exc_info=True)


async def start_delete_bot_posts():
    """Периодическая задача: удаление сообщений ботов по расписанию"""
    bot_posts = await db.get_bot_posts_for_clear_messages()

    for bot_post in bot_posts:
        if (bot_post.delete_time + bot_post.start_timestamp) > time.time():
            continue

        messages = bot_post.message_ids
        if not messages:
            continue

        for bot_id in list(messages.keys()):
            user_bot = await db.get_bot_by_id(int(bot_id))
            asyncio.create_task(delete_bot_posts(user_bot, messages[bot_id]["message_ids"]))


async def send_bot_messages(other_bot: Bot, bot_post: BotPost, users, filepath):
    """Отправить сообщения через бота"""
    message_options = MessageOptionsHello(**bot_post.message)

    if message_options.text:
        cor = other_bot.send_message
    elif message_options.photo:
        cor = other_bot.send_photo
        message_options.photo = types.FSInputFile(filepath)
    elif message_options.video:
        cor = other_bot.send_video
        message_options.video = types.FSInputFile(filepath)
    else:
        cor = other_bot.send_animation
        message_options.animation = types.FSInputFile(filepath)

    options = message_options.model_dump()

    try:
        options.pop("show_caption_above_media")
        options.pop("disable_web_page_preview")
        options.pop("has_spoiler")
    except KeyError:
        pass

    if message_options.text:
        options.pop("photo")
        options.pop("video")
        options.pop("animation")
        options.pop("caption")
    elif message_options.photo:
        options.pop("video")
        options.pop("animation")
        options.pop("text")
    elif message_options.video:
        options.pop("photo")
        options.pop("animation")
        options.pop("text")
    # animation
    else:
        options.pop("photo")
        options.pop("video")
        options.pop("text")

    options['parse_mode'] = 'HTML'

    success = 0
    message_ids = []

    for user in users:
        try:
            options["chat_id"] = user
            if bot_post.text_with_name:
                get_user = await other_bot.get_chat(user)
                added_text = f"{get_user.username or get_user.first_name}\\n\\n"

                if message_options.text:
                    options["text"] = added_text + message_options.text
                if message_options.caption:
                    options["caption"] = added_text + message_options.caption

            message = await cor(**options)
            message_ids.append({"message_id": message.message_id, "chat_id": user})
            success += 1
        except Exception as e:
            logger.error(f"Error sending bot message to user {user}: {e}", exc_info=True)

        await asyncio.sleep(0.25)

    return {other_bot.id: {"success": success, "message_ids": message_ids}}


async def process_bot(user_bot: UserBot, bot_post: BotPost, users, filepath):
    """Обработать отправку через бота"""
    async with BotManager(user_bot.token) as bot_manager:
        validate = await bot_manager.validate_token()

        if not validate:
            raise Exception("TOKEN")
        status = await bot_manager.status()
        if not status:
            raise Exception("STATUS")

        return await send_bot_messages(
            other_bot=bot_manager.bot,
            bot_post=bot_post,
            users=users,
            filepath=filepath
        )


async def send_bot_post(bot_post: BotPost):
    """Отправить пост через боты"""
    users_count = 0
    semaphore = asyncio.Semaphore(5)

    async def process_semaphore(*args):
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
        get_file = await bot.get_file(file_id)
        filepath = "main_bot/utils/temp/mail_{}".format(
            get_file.file_path.split("/")[-1]
        )

    tasks = []
    user_bot_objects = []

    for chat_id in bot_post.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        channel_settings = await db.get_channel_bot_setting(
            chat_id=channel.chat_id
        )
        user_bot = await db.get_bot_by_id(
            row_id=channel_settings.bot_id
        )

        other_db = Database()
        other_db.schema = user_bot.schema

        users = await other_db.get_users(channel.chat_id)
        users_count += len(users)

        tasks.append(
            process_semaphore(user_bot, bot_post, users, filepath)
        )
        user_bot_objects.append(channel)

    success_count = 0
    message_ids = {}

    start_timestamp = int(time.time())
    end_timestamp = int(time.time())
    
    if tasks:
        if file_id and filepath:
            await bot.download(file_id, filepath)

        result = await asyncio.gather(*tasks, return_exceptions=True)
        for i in result:
            if not isinstance(i, dict):
                continue

    if file_id and filepath:
        try:
            os.remove(filepath)
        except Exception as e:
            logger.error(f"Error removing file {filepath}: {e}", exc_info=True)

    await db.update_bot_post(
        post_id=bot_post.id,
        success_send=success_count,
        error_send=users_count - success_count,
        start_timestamp=start_timestamp,
        end_timestamp=end_timestamp,
        status=Status.FINISH,
        message_ids=message_ids or None
    )


async def send_bot_posts():
    """Периодическая задача: отправка постов через ботов"""
    posts = await db.get_bot_post_for_send()
    if not posts:
        return

    tasks = []
    for post in posts:
        asyncio.create_task(send_bot_post(post))

    await asyncio.gather(*tasks, return_exceptions=True)
