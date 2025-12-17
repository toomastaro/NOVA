import asyncio
import time

from loguru import logger

from aiogram import types, Router, F, Bot
from aiogram.enums import ChatMemberStatus

from instance_bot import bot as main_bot_obj
from hello_bot.database.db import Database
from hello_bot.utils.lang.language import text

from main_bot.database.channel_bot_captcha.model import ChannelCaptcha
from main_bot.database.channel_bot_hello.model import ChannelHelloMessage
from main_bot.utils.functions import answer_message_bot
from main_bot.utils.schemas import MessageOptionsCaptcha, MessageOptionsHello, ByeAnswer
from main_bot.database.user_bot.model import UserBot
from main_bot.database.db import db as main_db
from main_bot.keyboards import keyboards
from utils.functions import create_emoji


async def msg_handler(message: types.Message, db: Database):
    """
    Обрабатывает любые сообщения от пользователя в личке бота.
    
    Регистрирует пользователя или обновляет время последней активности (капчи).
    """
    user = await db.user.get_user(message.from_user.id)
    if not user:
        await db.user.add_user(
            id=message.from_user.id,
            walk_captcha=True,
            time_walk_captcha=int(time.time())
        )
    else:
        await db.user.update_user(
            user_id=message.from_user.id,
            walk_captcha=True,
            time_walk_captcha=int(time.time())
        )

    await message.delete()
    r = await message.answer(".", reply_markup=types.ReplyKeyboardRemove())
    await r.delete()


async def send_captcha(user_bot, user_id: int, db_obj: Database, captcha: ChannelCaptcha):
    """Отправляет сообщение с капчей пользователю."""
    if captcha.delay:
        while True:
            user = await db_obj.get_user(user_id)

            if not user or user.walk_captcha:
                return

            await answer_message_bot(user_bot, user_id, MessageOptionsCaptcha(**captcha.message))
            await asyncio.sleep(captcha.delay)  # type: ignore

    await answer_message_bot(user_bot, user_id, MessageOptionsCaptcha(**captcha.message))


async def send_hello(user_bot: Bot, user_id: int, db_obj: Database, hello_message: ChannelHelloMessage):
    """Отправляет приветственное сообщение."""
    message_options = MessageOptionsHello(**hello_message.message)

    if hello_message.text_with_name:
        get_user = await user_bot.get_chat(user_id)
        added_text = f"{get_user.username or get_user.first_name}\n\n"

        if message_options.text:
            message_options.text = added_text + message_options.text
        if message_options.caption:
            message_options.caption = added_text + message_options.caption

    if hello_message.delay and hello_message.delay == 1:
        while True:
            user = await db_obj.get_user(user_id)

            if not user.walk_captcha:
                await asyncio.sleep(3)
                continue

            await answer_message_bot(user_bot, user_id, message_options)
            return

    if hello_message.delay:
        await asyncio.sleep(hello_message.delay)  # type: ignore

    await answer_message_bot(user_bot, user_id, message_options)


async def join(call: types.ChatJoinRequest, db: Database):
    """
    Обрабатывает заявку на вступление в канал.

    Проверяет настройки канала, отправляет капчу или приветствие,
    и при необходимости автоматически одобряет заявку.
    """
    logger.debug(f"Join request: {call}")

    chat_id = call.chat.id
    invite_url = call.invite_link.name.lower()

    user = await db.user.get_user(call.from_user.id)
    if not user:
        await db.user.add_user(
            id=call.from_user.id,
            channel_id=chat_id,
            invite_url=invite_url
        )

    channel_settings = await main_db.get_channel_bot_setting(
        chat_id=chat_id
    )
    if not channel_settings:
        return

    logger.debug(f"Channel settings: {channel_settings}")
    logger.debug(f"Invite URL: {invite_url}")

    if "(aon)" in invite_url or "(aoff)" in invite_url:
        enable_auto_approve = "(aon)" in invite_url
    else:
        enable_auto_approve = None

    if "(con)" in invite_url or "(coff)" in invite_url:
        enable_captcha = "(con)" in invite_url
    else:
        enable_captcha = None

    if "(pon)" in invite_url or "(poff)" in invite_url:
        enable_hello = "(pon)" in invite_url
    else:
        enable_hello = None

    logger.debug(f"Flags -> Captcha: {enable_captcha}, Hello: {enable_hello}, AutoApprove: {enable_auto_approve}")

    if channel_settings.active_captcha_id:
        if enable_captcha is None or enable_captcha:
            captcha = await main_db.get_captcha(
                message_id=channel_settings.active_captcha_id
            )

            if captcha:
                asyncio.create_task(
                    send_captcha(
                        user_bot=call.bot,
                        user_id=call.from_user.id,
                        db_obj=db,
                        captcha=captcha
                    )
                )

    active_hello_messages = await main_db.get_hello_messages(
        chat_id=chat_id,
        active=True
    )
    logger.debug(f"Active hello messages: {active_hello_messages}")

    if active_hello_messages:
        if enable_hello is None or enable_hello:
            for hello_message in active_hello_messages:
                asyncio.create_task(
                    send_hello(
                        user_bot=call.bot,
                        user_id=call.from_user.id,
                        db_obj=db,
                        hello_message=hello_message
                    )
                )

    if channel_settings.auto_approve or enable_auto_approve:
        if channel_settings.auto_approve and channel_settings.delay_approve:
            if channel_settings.delay_approve == 1:
                while True:
                    user = await db.user.get_user(call.from_user.id)

                    if not user.walk_captcha:
                        await asyncio.sleep(3)
                        continue

                    break

            await asyncio.sleep(channel_settings.delay_approve)

        try:
            await call.approve()
            await db.user.update_user(
                user_id=call.from_user.id,
                is_approved=True,
                time_approved=int(time.time())
            )
        except Exception as e:
            logger.error(f"Ошибка при одобрении заявки: {e}")


async def leave(call: types.ChatMemberUpdated, db: Database):
    """
    Обрабатывает выход пользователя из канала.

    Если настроено прощальное сообщение (bye), отправляет его пользователю.
    """
    if call.new_chat_member.user.is_bot:
        return
    if call.new_chat_member.status != ChatMemberStatus.LEFT:
        return

    settings = await main_db.get_channel_bot_setting(
        chat_id=call.chat.id
    )
    if not settings:
        return

    user = await db.user.get_user(call.from_user.id)
    if not user:
        await db.user.add_user(id=call.from_user.id)

    bye = ByeAnswer(**settings.bye)
    if not bye.active:
        return

    await answer_message_bot(call.bot, call.from_user.id, bye.message)


async def set_channel(call: types.ChatMemberUpdated, db_bot: UserBot):
    """
    Обрабатывает добавление бота в канал администратором.

    Настраивает связь бота с каналом в базе данных.
    """
    chat_id = call.chat.id

    channel = await main_db.get_channel_by_chat_id(
        chat_id=chat_id
    )
    if not channel:
        return

    exist = await main_db.get_channel_bot_setting(chat_id)

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR and (not exist or not exist.bot_id):
        chat = await call.bot.get_chat(chat_id)
        if chat.photo:
            photo_bytes = await call.bot.download(chat.photo.big_file_id)
        else:
            photo_bytes = None

        _emoji_id = await create_emoji(call.from_user.id, photo_bytes)

        if not exist:
            await main_db.add_channel_bot_setting(
                id=chat_id,
                bot_id=db_bot.id,
                admin_id=db_bot.admin_id,
                bye=ByeAnswer().model_dump()
            )
        else:
            await main_db.update_channel_bot_setting(
                chat_id=chat_id,
                bot_id=db_bot.id,
                admin_id=db_bot.admin_id,
            )

        message_text = text('success_connect_bot_channel').format(
            db_bot.username,
            call.chat.title
        )
    else:
        await main_db.update_channel_bot_setting(
            chat_id=chat_id,
            bot_id=None
        )

        message_text = text('success_delete_channel').format(
            channel.title
        )

    try:
        await main_bot_obj.send_message(
            chat_id=call.from_user.id,
            text=message_text
        )

        bot_database = Database()
        bot_database.schema = db_bot.schema
        count_users = await bot_database.get_count_users()

        channel_ids_in_bot = await main_db.get_all_channels_in_bot_id(
            bot_id=db_bot.id
        )
        channels = [
            await main_db.get_channel_by_chat_id(chat.id)
            for chat in channel_ids_in_bot
        ]

        status = True

        await main_bot_obj.send_message(
            chat_id=call.from_user.id,
            text=text("bot:info").format(
                db_bot.title,
                "\n".join(
                    text("resource_title").format(
                        channel.title
                    ) for channel in channels
                ) if channels else "❌",
                "✅" if status else "❌",
                count_users.get("active"),
                count_users.get("total"),
            ),
            reply_markup=keyboards.manage_bot(
                user_bot=db_bot,
                status=status
            )
        )

    except Exception as e:
        logger.error(f"Ошибка при настройке канала: {e}")


async def set_active(call: types.ChatMemberUpdated, db: Database):
    """Обновляет статус активности пользователя (блокировка бота)."""
    await db.user.update_user(
        user_id=call.from_user.id,
        is_active=call.new_chat_member.status != ChatMemberStatus.KICKED
    )


def hand_add():
    """Регистрация хендлеров пользователя для hello_bot."""
    router = Router()
    router.message.register(msg_handler)

    router.chat_join_request.register(join)
    router.chat_member.register(leave, F.chat.type == "channel")
    router.my_chat_member.register(set_channel, F.chat.type == 'channel')
    router.my_chat_member.register(set_active, F.chat.type == 'private')

    return router
