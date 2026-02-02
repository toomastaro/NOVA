import asyncio
import time

from loguru import logger

from aiogram import types, Router, F, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest

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
from utils.error_handler import safe_handler
from hello_bot.utils.events import event_manager


@safe_handler("Личка: любое сообщение")
async def msg_handler(message: types.Message, db: Database):
    """
    Обрабатывает любые сообщения от пользователя в личке бота.

    Регистрирует пользователя или обновляет время последней активности (капчи).
    """
    user = await db.get_user(message.from_user.id)
    if not user:
        await db.add_user(
            id=message.from_user.id,
            walk_captcha=True,
            time_walk_captcha=int(time.time()),
        )
    else:
        # Удаляем сообщение с капчей, если оно было сохранено
        if user.captcha_message_id:
            try:
                await message.bot.delete_message(
                    chat_id=message.from_user.id,
                    message_id=user.captcha_message_id
                )
                logger.info(f"Удалено сообщение капчи {user.captcha_message_id} для пользователя {message.from_user.id}")
            except Exception as e:
                logger.warning(f"Не удалось удалить сообщение капчи: {e}")

        await db.update_user(
            user_id=message.from_user.id,
            walk_captcha=True,
            time_walk_captcha=int(time.time()),
            captcha_message_id=None,
        )

    # Уведомляем систему, что капча пройдена
    event_manager.notify(db.schema, message.from_user.id)

    # Пытаемся удалить сообщение пользователя (в личке это невозможно, но в группах может сработать)
    try:
        await message.delete()
    except TelegramBadRequest:
        pass  # Игнорируем ошибку, если у бота нет прав или это личка

    r = await message.answer(".", reply_markup=types.ReplyKeyboardRemove())
    try:
        await r.delete()
    except TelegramBadRequest:
        pass


@safe_handler("Вход: отправка капчи (Background)")
async def send_captcha(
    user_bot, user_id: int, db_obj: Database, captcha: ChannelCaptcha
):
    """Отправляет сообщение с капчей пользователю."""
    if captcha.start_delay:
        await asyncio.sleep(captcha.start_delay)

    if captcha.delay:
        while True:
            # Ожидаем прохождения капчи в течение delay секунд
            passed = await event_manager.wait_for(
                db_obj.schema, user_id, timeout=captcha.delay
            )
            if passed:
                logger.info(f"Пользователь {user_id} прошел капчу (через событие)")
                return

            # Если таймаут — проверяем статус в БД (на случай перезагрузки или рассинхрона)
            user = await db_obj.get_user(user_id)
            if not user or user.walk_captcha:
                return

            # Шлем напоминание, так как капча все еще не пройдена
            sent_msg = await answer_message_bot(
                user_bot, user_id, MessageOptionsCaptcha(**captcha.message)
            )
            if sent_msg:
                await db_obj.update_user(
                    user_id=user_id, captcha_message_id=sent_msg.message_id
                )

    sent_msg = await answer_message_bot(
        user_bot, user_id, MessageOptionsCaptcha(**captcha.message)
    )
    if sent_msg:
        await db_obj.update_user(
            user_id=user_id, captcha_message_id=sent_msg.message_id
        )


@safe_handler("Вход: отправка приветствия (Background)")
async def send_hello(
    user_bot: Bot, user_id: int, db_obj: Database, hello_message: ChannelHelloMessage
):
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
        logger.debug(
            f"Ожидание прохождения капчи для отправки Hello пользователю {user_id}"
        )
        # Ждем прохождения капчи (без polling)
        await event_manager.wait_for(db_obj.schema, user_id)

        await answer_message_bot(user_bot, user_id, message_options, None)
        return

    if hello_message.delay:
        await asyncio.sleep(hello_message.delay)  # type: ignore

    await answer_message_bot(user_bot, user_id, message_options)


@safe_handler("Канал: запрос на вступление")
async def join(call: types.ChatJoinRequest, db: Database):
    """
    Обрабатывает заявку на вступление в канал.

    Выполняет следующие шаги:
    1. Регистрация или обновление данных пользователя (сброс статуса одобрения).
    2. Получение настроек канала.
    3. Обработка флагов инвайт-ссылки.
    4. Отправка капчи или приветствия (фоновые задачи).
    5. Автоматическое одобрение заявки с учетом задержки (независимо от капчи).

    Аргументы:
        call (types.ChatJoinRequest): Объект запроса от Telegram.
        db (Database): Объект базы данных текущего бота.
    """
    logger.info(f"ХЕНДЛЕР JOIN ВЫЗВАН: пользователь {call.from_user.id} стучится в чат {call.chat.id}")
    user_id = call.from_user.id
    chat_id = call.chat.id
    invite_url = (
        call.invite_link.name.lower()
        if call.invite_link and call.invite_link.name
        else ""
    )

    logger.debug(
        f"Получен запрос на вступление: пользователь {user_id}, чат {chat_id}, ссылка '{invite_url}'"
    )

    # Регистрация или обновление пользователя
    # КРИТИЧНО: Сбрасываем is_approved в False при каждой новой заявке, 
    # чтобы счетчик накопленных заявок работал корректно
    user = await db.get_user(user_id)
    if not user:
        logger.info(f"Новый пользователь {user_id} регистрируется через заявку")
        await db.add_user(
            id=user_id, channel_id=chat_id, invite_url=invite_url, is_approved=False
        )
    else:
        logger.debug(f"Пользователь {user_id} обновляет заявку для канала {chat_id}")
        await db.update_user(
            user_id=user_id,
            channel_id=chat_id,
            invite_url=invite_url,
            is_approved=False,  # Сбрасываем статус одобрения для новой заявки
        )

    # Получаем настройки из основной БД
    channel_settings = await main_db.channel_bot_settings.get_channel_bot_setting(
        chat_id=chat_id
    )
    if not channel_settings:
        logger.warning(f"Настройки для чата {chat_id} не найдены")
        return

    # Обработка переопределений в ссылках (AON/AOFF, CON/COFF, PON/POFF)
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

    # Отправка капчи (если настроена)
    if channel_settings.active_captcha_id:
        if enable_captcha is None or enable_captcha:
            captcha = await main_db.channel_bot_captcha.get_captcha(
                message_id=channel_settings.active_captcha_id
            )
            if captcha:
                logger.info(f"Запуск задачи капчи для пользователя {user_id}")
                asyncio.create_task(
                    send_captcha(
                        user_bot=call.bot,
                        user_id=user_id,
                        db_obj=db,
                        captcha=captcha,
                    )
                )

    # Отправка приветственных сообщений (если есть)
    active_hello_messages = await main_db.channel_bot_hello.get_hello_messages(
        chat_id=chat_id, active=True
    )
    if active_hello_messages:
        if enable_hello is None or enable_hello:
            logger.info(
                f"Запуск задач приветствия ({len(active_hello_messages)}) для пользователя {user_id}"
            )
            for hello_message in active_hello_messages:
                asyncio.create_task(
                    send_hello(
                        user_bot=call.bot,
                        user_id=user_id,
                        db_obj=db,
                        hello_message=hello_message,
                    )
                )

    # Логика автоматического одобрения (теперь НЕЗАВИСИМА от капчи)
    should_approve = (
        channel_settings.auto_approve
        if enable_auto_approve is None
        else enable_auto_approve
    )

    logger.info(
        f"ОТЛАДКА: Пользователь {user_id}, Чат {chat_id}, Настройка: {channel_settings.auto_approve}, Флаг ссылки: {enable_auto_approve}, Итог: {should_approve}"
    )

    if should_approve:
        logger.info(f"Начинается процесс авто-одобрения для пользователя {user_id}")

        # Если настроена задержка
        if channel_settings.delay_approve > 0:
            delay = channel_settings.delay_approve
            # Если выбрано "После капчи" (1), трактуем как минимальную задержку 1 сек
            if delay == 1:
                delay = 1
                logger.info("Задержка 'После капчи' заменена на 1 сек (независимое одобрение)")
            
            logger.info(f"Задержка одобрения {delay} сек для пользователя {user_id}")
            await asyncio.sleep(delay)

        # Одобрение заявки
        try:
            await call.approve()
            await db.update_user(
                user_id=user_id,
                is_approved=True,
                time_approved=int(time.time()),
            )
            logger.info(
                f"Заявка пользователя {user_id} УСПЕШНО одобрена в чате {chat_id}"
            )
        except Exception as e:
            logger.error(f"ОШИБКА при одобрении заявки пользователя {user_id}: {e}")
    else:
        logger.info(f"Авто-одобрение отключено для запроса пользователя {user_id}")


@safe_handler("Канал: выход пользователя")
async def leave(call: types.ChatMemberUpdated, db: Database):
    """
    Обрабатывает выход пользователя из канала.

    Если настроено прощальное сообщение (bye), отправляет его пользователю.
    """
    if call.new_chat_member.user.is_bot:
        return
    if call.new_chat_member.status != ChatMemberStatus.LEFT:
        return

    settings = await main_db.channel_bot_settings.get_channel_bot_setting(
        chat_id=call.chat.id
    )
    if not settings:
        return

    user = await db.get_user(call.from_user.id)
    if not user:
        await db.add_user(id=call.from_user.id)

    bye = ByeAnswer(**settings.bye)
    if not bye.active:
        return

    await answer_message_bot(call.bot, call.from_user.id, bye.message)


@safe_handler("Канал: изменение прав бота")
async def set_channel(call: types.ChatMemberUpdated, db_bot: UserBot):
    """
    Обрабатывает добавление бота в канал администратором.

    Настраивает связь бота с каналом в базе данных.
    """
    chat_id = call.chat.id
    if call.from_user.is_bot:
        return

    channel = await main_db.channel.get_channel_by_chat_id(chat_id=chat_id)
    if not channel:
        return

    exist = await main_db.channel_bot_settings.get_channel_bot_setting(chat_id)

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR and (
        not exist or not exist.bot_id
    ):
        if not exist:
            await main_db.channel_bot_settings.add_channel_bot_setting(
                id=chat_id,
                bot_id=db_bot.id,
                admin_id=db_bot.admin_id,
                bye=ByeAnswer().model_dump(),
            )
        else:
            await main_db.channel_bot_settings.update_channel_bot_setting(
                chat_id=chat_id,
                bot_id=db_bot.id,
                admin_id=db_bot.admin_id,
            )

        message_text = text("success_connect_bot_channel").format(
            db_bot.username, call.chat.title
        )
    else:
        await main_db.channel_bot_settings.update_channel_bot_setting(
            chat_id=chat_id, bot_id=None
        )

        message_text = text("success_delete_channel").format(
            db_bot.emoji_id, db_bot.username, db_bot.emoji_id, channel.title
        )

    try:
        await main_bot_obj.send_message(chat_id=call.from_user.id, text=message_text)

        bot_database = Database()
        bot_database.schema = db_bot.schema
        count_users = await bot_database.get_count_users()

        channel_ids_in_bot = (
            await main_db.channel_bot_settings.get_all_channels_in_bot_id(
                bot_id=db_bot.id
            )
        )
        channels_raw = [
            await main_db.channel.get_channel_admin_row(
                chat_id=chat.id, user_id=call.from_user.id
            )
            for chat in channel_ids_in_bot
        ]
        channels = [c for c in channels_raw if c]

        status = True

        await main_bot_obj.send_message(
            chat_id=call.from_user.id,
            text=text("bot:info").format(
                db_bot.title,
                (
                    "\n".join(
                        text("resource_title").format(channel.title)
                        for channel in channels
                    )
                    if channels
                    else "❌"
                ),
                "✅" if status else "❌",
                count_users.get("active"),
                count_users.get("total"),
            ),
            reply_markup=keyboards.manage_bot(user_bot=db_bot, status=status),
        )

    except Exception as e:
        logger.error(f"Ошибка при настройке канала: {e}")


@safe_handler("Личка: статус активности")
async def set_active(call: types.ChatMemberUpdated, db: Database):
    """Обновляет статус активности пользователя (блокировка бота)."""
    await db.update_user(
        user_id=call.from_user.id,
        is_active=call.new_chat_member.status != ChatMemberStatus.KICKED,
    )


def hand_add():
    """Регистрация хендлеров пользователя для hello_bot."""
    router = Router()
    router.message.register(msg_handler)

    router.chat_join_request.register(join)
    router.chat_member.register(leave, F.chat.type == "channel")
    router.my_chat_member.register(set_channel, F.chat.type == "channel")
    router.my_chat_member.register(set_active, F.chat.type == "private")

    return router
