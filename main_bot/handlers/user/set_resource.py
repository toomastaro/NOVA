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
from main_bot.utils.functions import set_channel_session
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


def _get_instruction_text(
    chat_title: str, username: str, first_name: str = "Assistant"
) -> str:
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


@safe_handler("Set Admins", log_start=False)
async def set_admins(
    bot: Bot,
    chat_id: int,
    chat_title: str,
    emoji_id: str,
    user_id: Optional[int] = None,
) -> None:
    """
    Добавляет администраторов канала в базу данных.
    """
    # Добавляем того, кто инициировал (чтобы сразу отобразилось в списке)
    if user_id:
        await db.channel.add_channel(
            chat_id=chat_id, title=chat_title, admin_id=user_id, emoji_id=emoji_id
        )

    try:
        admins = await bot.get_chat_administrators(chat_id)
    except Exception:
        logger.error("Ошибка получения администраторов канала %s", chat_id)
        return

    # Добавляем остальных админов
    for admin in admins:
        if admin.user.is_bot or admin.user.id == user_id:
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


@safe_handler("Setup Channel Task", log_start=False)
async def setup_channel_task(
    bot: Bot, chat_id: int, chat_title: str, user_id: int
) -> None:
    """Фоновая задача настройки канала"""
    # 1. Настройка админов
    await set_admins(bot, chat_id, chat_title, "5393222813345663485", user_id=user_id)

    # 2. Назначаем клиента (самое долгое)
    res = await set_channel_session(chat_id)

    # 3. Планирование статистики
    channel_obj = await db.channel.get_channel_by_chat_id(chat_id)
    if channel_obj and scheduler_instance:
        schedule_channel_job(scheduler_instance, channel_obj)
        asyncio.create_task(update_channel_stats(chat_id))

    # 4. Отправка инструкции
    if res.get("success"):
        client_info = res.get("client_info", {})
        username = client_info.get("username", "username")
        first_name = client_info.get("first_name", "Assistant")
        message_text = _get_instruction_text(chat_title, username, first_name)
    else:
        message_text = (
            text("success_add_channel").format(chat_title)
            + "\n\n⚠️ Не удалось назначить помощника автоматически. Пожалуйста, обратитесь в поддержку."
        )

    try:
        await bot.send_message(chat_id=user_id, text=message_text)
    except Exception:
        logger.error(f"Не удалось отправить инструкцию пользователю {user_id}")


@safe_handler("Set Channel")
async def set_channel(call: types.ChatMemberUpdated) -> None:
    """
    Обработчик события добавления/удаления бота в канале.
    """
    chat_id = call.chat.id
    channel = await db.channel.get_channel_by_chat_id(chat_id=chat_id)

    if call.new_chat_member.status == ChatMemberStatus.ADMINISTRATOR:
        if channel:
            return

        chat_title = call.chat.title or f"Channel {chat_id}"

        # Быстрый ответ пользователю
        await call.bot.send_message(
            chat_id=call.from_user.id,
            text=f"⏳ <b>Добавляю канал «{chat_title}»...</b>\n\nЭто займет несколько секунд, я настраиваю помощника.",
        )

        # Фоновая настройка
        asyncio.create_task(
            setup_channel_task(call.bot, chat_id, chat_title, call.from_user.id)
        )
    else:
        if not channel:
            return

        await db.channel.delete_channel(chat_id=chat_id)
        await call.bot.send_message(
            chat_id=call.from_user.id,
            text=text("success_delete_channel").format(channel.title),
        )


@safe_handler("Set Admin", log_start=False)
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
    """
    chat_id = None
    chat_title = None

    # 1. Определяем chat_id
    if message.forward_from_chat and message.forward_from_chat.type == "channel":
        chat_id = message.forward_from_chat.id
        chat_title = message.forward_from_chat.title
    else:
        text_val = message.text.strip()
        if text_val.startswith("@") or "t.me/" in text_val:
            try:
                if "t.me/" in text_val:
                    username = text_val.split("t.me/")[-1].split("/")[0]
                    if not username.startswith("@"):
                        username = f"@{username}"
                else:
                    username = text_val

                chat = await message.bot.get_chat(username)
                if chat.type == "channel":
                    chat_id = chat.id
                    chat_title = chat.title
            except Exception:
                pass

    if not chat_id:
        return await message.answer(
            "❌ <b>Не удалось найти канал.</b>\n\nУбедитесь, что канал публичный и вы отправили правильную ссылку или переслали пост."
        )

    # 2. Проверка прав бота (минимум для продолжения)
    try:
        bot_member = await message.bot.get_chat_member(chat_id, message.bot.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            return await message.answer(
                "❌ <b>Бот не является администратором в канале.</b>\n\nСначала добавьте @novatg в админы канала с правом публикации."
            )
    except Exception as e:
        logger.error("Ошибка проверки прав бота в %s: %s", chat_id, e)
        return await message.answer(
            "❌ <b>Бот не найден в канале.</b>\n\nДобавьте @novatg в администраторы канала и попробуйте снова."
        )

    # 3. Проверка прав пользователя
    user_member = await message.bot.get_chat_member(chat_id, message.from_user.id)
    if user_member.status not in [
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.CREATOR,
    ]:
        return await message.answer("❌ Вы должны быть администратором этого канала.")

    # 4. Быстрый ответ и запуск фоновой задачи
    await message.answer(
        f"⏳ <b>Добавляю канал «{chat_title}»...</b>\n\nЯ настраиваю помощника и собираю первую статистику, это займет немного времени.",
        parse_mode="HTML",
    )

    # Запускаем фоновую инициализацию
    asyncio.create_task(
        setup_channel_task(message.bot, chat_id, chat_title, message.from_user.id)
    )

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
