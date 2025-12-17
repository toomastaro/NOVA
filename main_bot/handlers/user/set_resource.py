"""
Обработчики добавления каналов и управления правами.

Модуль обрабатывает:
- Добавление бота в каналы (автоматическое и ручное)
- Изменение прав администраторов
- Отслеживание статуса бота и пользователей
"""
import asyncio
import logging
from typing import Optional

from aiogram import types, F, Router, Bot
from aiogram.enums import ChatMemberStatus
from aiogram.fsm.context import FSMContext

from main_bot.states.user import AddChannel
from main_bot.handlers.user.menu import start_posting

from main_bot.database.db import db
from main_bot.utils.schedulers import (
    schedule_channel_job,
    update_channel_stats,
    scheduler_instance,
)
from main_bot.utils.functions import create_emoji, set_channel_session
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


def _get_instruction_text(chat_title: str, username: str, first_name: str = "Assistant") -> str:
    """
    Формирует текст инструкции по добавлению помощника.

    Аргументы:
        chat_title (str): Название канала.
        username (str): Юзернейм бота-помощника.
        first_name (str): Имя бота-помощника.

    Возвращает:
        str: Текст инструкции.
    """
    return (
        f"✅ <b>Канал «{chat_title}» успешно добавлен!</b>\n\n"
        f"⚠️ <b>ВАЖНО: Требуется настройка помощника</b>\n\n"
        f"Для работы функций постинга и историй, вам необходимо вручную добавить нашего помощника в администраторы канала.\n\n"
        f"👤 <b>Помощник:</b> {first_name} (@{username})\n\n"
        f"📋 <b>Инструкция:</b>\n"
        f"1. Зайдите в настройки канала -> Администраторы -> Добавить администратора.\n"
        f"2. В поиске введите: @{username}\n"
        f"3. Выберите этого пользователя и выдайте следующие права:\n"
        f"   ✅ Публикация сообщений\n"
        f"   ✅ Редактирование сообщений\n"
        f"   ✅ Удаление сообщений\n"
        f"   ✅ Публикация историй\n"
        f"   ✅ Редактирование историй\n"
        f"   ✅ Удаление историй\n\n"
        f"После добавления и выдачи прав, перейдите в меню информации о канале и нажмите <b>«Проверить права помощника»</b>."
    )


@safe_handler("Set Admins")
async def set_admins(
    bot: Bot, chat_id: int, chat_title: str, emoji_id: str, user_id: Optional[int] = None
) -> None:
    """
    Добавляет администраторов канала в базу данных.
    Если бот еще не добавлен в канал (например, при ручном добавлении),
    добавляет только пользователя, который инициировал добавление.

    Аргументы:
        bot (Bot): Экземпляр бота.
        chat_id (int): ID канала.
        chat_title (str): Название канала.
        emoji_id (str): ID эмодзи (аватарки канала).
        user_id (Optional[int]): ID пользователя-инициатора (для ручного добавления).
    """
    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception:
        logger.error("Ошибка получения администраторов канала %s", chat_id)
        # Если не можем получить список админов, добавляем хотя бы того, кто добавил бота
        if user_id:
            await db.channel.add_channel(
                chat_id=chat_id, title=chat_title, admin_id=user_id, emoji_id=emoji_id
            )
        return

    for admin in admins:
        if admin.user.is_bot:
            continue

        if not isinstance(admin, types.ChatMemberOwner):
            rights = {
                admin.can_post_messages,
                admin.can_edit_messages,
                admin.can_delete_messages,
                admin.can_post_stories,
                admin.can_edit_stories,
                admin.can_delete_stories,
            }
            if False in rights:
                continue

        await db.channel.add_channel(
            chat_id=chat_id, title=chat_title, admin_id=admin.user.id, emoji_id=emoji_id
        )


@safe_handler("Set Channel")
async def set_channel(call: types.ChatMemberUpdated) -> None:
    """
    Обработчик события добавления/удаления бота в канале.
    Автоматически регистрирует канал при добавлении бота в админы.

    Аргументы:
        call (types.ChatMemberUpdated): Событие обновления прав бота.
    """
    chat_id = call.chat.id
    channel = await db.channel.get_channel_by_chat_id(chat_id=chat_id)

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        if channel:
            return

        # Обработка ошибок при получении информации о канале
        try:
            chat = await call.bot.get_chat(chat_id)
            chat_title = chat.title
            photo = chat.photo
        except Exception:
            logger.error("Ошибка получения информации о канале %s", chat_id)
            chat_title = call.chat.title
            photo = None

        # Загрузка фото канала
        if photo:
            try:
                photo_bytes = await call.bot.download(photo.big_file_id)
            except Exception:
                logger.error("Ошибка загрузки фото канала %s", chat_id)
                photo_bytes = None
        else:
            photo_bytes = None

        emoji_id = await create_emoji(call.from_user.id, photo_bytes)
        await set_admins(
            call.bot, chat_id, chat_title, emoji_id, user_id=call.from_user.id
        )

        # Назначаем клиента и получаем инструкцию
        res = await set_channel_session(chat_id)

        # Планирование задачи сбора статистики
        channel_obj = await db.channel.get_channel_by_chat_id(chat_id)
        if channel_obj and scheduler_instance:
            schedule_channel_job(scheduler_instance, channel_obj)
            asyncio.create_task(update_channel_stats(chat_id))

        if res.get("success"):
            client_info = res.get("client_info", {})
            username = client_info.get("username", "username")
            message_text = _get_instruction_text(chat_title, username)
        else:
            message_text = (
                text("success_add_channel").format(chat_title)
                + "\n\n⚠️ Не удалось назначить помощника. Обратитесь в поддержку."
            )

    else:
        if not channel:
            return

        await db.channel.delete_channel(chat_id=chat_id)

        message_text = text("success_delete_channel").format(channel.title)

    if call.from_user.is_bot:
        return

    await call.bot.send_message(
        chat_id=call.from_user.id, text=message_text, parse_mode="HTML"
    )


@safe_handler("Set Admin")
async def set_admin(call: types.ChatMemberUpdated) -> None:
    """
    Обработчик изменения прав участников канала.
    Отслеживает вступление по пригласительным ссылкам (для рекламы) и изменение списка админов.

    Аргументы:
        call (types.ChatMemberUpdated): Событие обновления прав участника.
    """
    if call.new_chat_member.user.is_bot:
        return

    chat_id = call.chat.id

    chat_id = call.chat.id

    # Отслеживание подписки для рекламных закупок, если пользователь вступил по ссылке
    if call.new_chat_member.status == ChatMemberStatus.MEMBER:
        if call.invite_link:
            try:
                await db.ad_purchase.process_join_event(
                    channel_id=chat_id,
                    user_id=call.new_chat_member.user.id,
                    invite_link=call.invite_link.invite_link,
                )
            except Exception:
                # Игнорируем ошибки отслеживания
                pass

    # Отслеживание отписки (Left/Kicked)
    if call.new_chat_member.status in [ChatMemberStatus.LEFT, ChatMemberStatus.KICKED]:
        try:
            await db.ad_purchase.update_subscription_status(
                user_id=call.new_chat_member.user.id, channel_id=chat_id, status="left"
            )
        except Exception:
            pass

    if call.new_chat_member.status == ChatMemberStatus.MEMBER:
        await db.channel.delete_channel(
            chat_id=chat_id, user_id=call.new_chat_member.user.id
        )

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        admin = call.new_chat_member
        rights = {
            admin.can_post_messages,
            admin.can_edit_messages,
            admin.can_delete_messages,
            admin.can_post_stories,
            admin.can_edit_stories,
            admin.can_delete_stories,
        }
        if False in rights:
            return await db.channel.delete_channel(
                chat_id=chat_id, user_id=admin.user.id
            )

        channel = await db.channel.get_channel_by_chat_id(chat_id)
        await db.channel.add_channel(
            chat_id=chat_id,
            admin_id=admin.user.id,
            title=call.chat.title,
            subscribe=channel.subscribe,
            session_path=channel.session_path,
            emoji_id=channel.emoji_id,
            created_timestamp=channel.created_timestamp,
        )


@safe_handler("Set Active")
async def set_active(call: types.ChatMemberUpdated) -> None:
    """
    Обновляет статус активности пользователя (blocked/unblocked bot).

    Аргументы:
        call (types.ChatMemberUpdated): Событие обновления статуса участника в ЛС.
    """
    await db.user.update_user(
        user_id=call.from_user.id,
        is_active=call.new_chat_member.status != ChatMemberStatus.KICKED,
    )


@safe_handler("Manual Add Channel")
async def manual_add_channel(message: types.Message, state: FSMContext) -> None:
    """
    Ручное добавление канала через отправку ссылки или форвард.
    Используется, если автоматическое добавление не сработало.

    Аргументы:
        message (types.Message): Сообщение с ссылкой или форвардом.
        state (FSMContext): Контекст состояния.
    """
    chat_id = None

    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        chat_id = message.forward_from_chat.id
    else:
        text_val = message.text.strip()
        if text_val.startswith("@") or "t.me/" in text_val:
            try:
                # Извлечение юзернейма, если это ссылка
                if "t.me/" in text_val:
                    username = text_val.split("t.me/")[-1].split("/")[0]
                    if not username.startswith("@"):
                        username = f"@{username}"
                else:
                    username = text_val

                chat = await message.bot.get_chat(username)
                if chat.type == "channel":
                    chat_id = chat.id
            except Exception:
                pass

    if not chat_id:
        await message.answer(
            "Не удалось определить канал. Пожалуйста, перешлите сообщение из канала или отправьте ссылку/юзернейм канала (например @channel)."
        )
        return

    # Проверка, является ли бот админом
    try:
        bot_member = await message.bot.get_chat_member(
            chat_id, (await message.bot.get_me()).id
        )
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            await message.answer(
                "Бот не является администратором этого канала. Пожалуйста, добавьте бота в администраторы и попробуйте снова."
            )
            return
    except Exception as e:
        # Бот не является членом канала - не показываем сообщение пользователю
        logger.error("Бот не является членом канала %s: %s", chat_id, e)
        return

    # Проверка, является ли пользователь админом
    user_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
    if user_member.status not in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    ]:
        await message.answer("Вы не являетесь администратором этого канала.")
        return

    # Логика добавления канала
    try:
        chat = await message.bot.get_chat(chat_id)
        chat_title = chat.title
        photo = chat.photo
    except Exception:
        logger.error("Ошибка получения информации о канале %s", chat_id)
        # Получаем информацию из user_member
        try:
            chat_info = await message.bot.get_chat(chat_id)
            chat_title = chat_info.title
            photo = None
        except Exception:
            chat_title = f"Channel {chat_id}"
            photo = None

    # Загрузка фото канала
    if photo:
        try:
            photo_bytes = await message.bot.download(photo.big_file_id)
        except Exception:
            logger.error("Ошибка загрузки фото канала %s", chat_id)
            photo_bytes = None
    else:
        photo_bytes = None

    emoji_id = await create_emoji(message.from_user.id, photo_bytes)

    await set_admins(
        message.bot, chat_id, chat_title, emoji_id, user_id=message.from_user.id
    )

    # Назначаем клиента и получаем инструкцию
    res = await set_channel_session(chat_id)

    # Планирование задачи сбора статистики
    channel_obj = await db.channel.get_channel_by_chat_id(chat_id)
    if channel_obj and scheduler_instance:
        schedule_channel_job(scheduler_instance, channel_obj)
        asyncio.create_task(update_channel_stats(chat_id))

    if res.get("success"):
        client_info = res.get("client_info", {})
        first_name = client_info.get("first_name", "Assistant")
        username = client_info.get("username", "username")

        msg = _get_instruction_text(chat_title, username, first_name)
    else:
        msg = (
            text("success_add_channel").format(chat_title)
            + "\n\n⚠️ Не удалось назначить помощника. Обратитесь в поддержку."
        )

    await message.answer(msg, parse_mode="HTML")
    await state.clear()
    await start_posting(message)


def get_router() -> Router:
    """
    Регистрация роутеров для управления каналами.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.my_chat_member.register(set_channel, F.chat.type == "channel")
    router.my_chat_member.register(set_active, F.chat.type == "private")
    router.chat_member.register(set_admin, F.chat.type == "channel")

    router.message.register(manual_add_channel, AddChannel.waiting_for_channel)

    return router
