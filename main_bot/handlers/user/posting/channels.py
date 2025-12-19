from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from pathlib import Path
import time
import asyncio

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import AddChannel
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
import logging
from utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


@safe_handler(
    "Постинг: фоновая проверка прав"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def check_permissions_task(chat_id: int):
    """Фоновая задача для обновления прав помощника."""
    from main_bot.utils.session_manager import SessionManager
    from main_bot.utils.tg_utils import db

    # 1. Получение клиента
    client_row = await db.mt_client_channel.get_my_membership(chat_id)
    if not client_row or not client_row[0].client:
        return

    mt_client = client_row[0].client
    session_path = Path(mt_client.session_path)
    if not session_path.exists():
        return

    # 2. Проверка прав
    try:
        async with SessionManager(session_path) as manager:
            perms = await manager.check_permissions(chat_id)
            logger.debug(f"Rights for {chat_id}: {perms}")

        if perms.get("error") == "USER_NOT_PARTICIPANT":
            # Сброс прав в БД, если помощника нет в канале
            await db.mt_client_channel.set_membership(
                client_id=mt_client.id,
                channel_id=chat_id,
                is_member=False,
                is_admin=False,
                can_post_stories=False,
                last_joined_at=int(time.time()),
                preferred_for_stats=client_row[0].preferred_for_stats,
            )
            logger.info(
                f"Статус помощника сброшен для {chat_id} (удален из участников)"
            )
            return

        if not perms.get("error"):
            is_admin = perms.get("is_admin", False)
            can_post = perms.get("can_post_messages", False)
            can_stories = perms.get("can_post_stories", False)

            # 3. Обновление БД
            await db.mt_client_channel.set_membership(
                client_id=mt_client.id,
                channel_id=chat_id,
                is_member=perms.get("is_member", True),
                is_admin=is_admin,
                can_post_messages=can_post,
                can_post_stories=can_stories,
                last_joined_at=int(time.time()),
                preferred_for_stats=client_row[0].preferred_for_stats,
            )
    except Exception as e:
        logger.error(f"Ошибка в check_permissions_task: {e}")


@safe_handler(
    "Постинг: информация о канале"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def render_channel_info(
    call: types.CallbackQuery, state: FSMContext, channel_id: int
):
    """Отображает информацию о канале (статистика, статус, редакторы)."""
    channels = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="posting"
    )

    channel = await db.channel.get_channel_by_chat_id(channel_id)
    if not channel:
        # Если канал удален
        return await call.message.edit_text(
            text=text("channels_text"),
            reply_markup=keyboards.channels(channels=channels),
        )

    editors_str = await get_editors(call, channel.chat_id)

    # Получаем информацию о создателе
    try:
        creator = await call.bot.get_chat(channel.admin_id)
        creator_name = f"@{creator.username}" if creator.username else creator.full_name
    except Exception:
        creator_name = "Неизвестно"

    # Получаем количество подписчиков
    try:
        members_count = await call.bot.get_chat_member_count(channel.chat_id)
    except Exception:
        members_count = "N/A"

    # Форматируем дату добавления
    from datetime import datetime

    created_date = datetime.fromtimestamp(channel.created_timestamp)
    created_str = created_date.strftime("%d.%m.%Y в %H:%M")

    # Статус подписки
    if channel.subscribe:
        from datetime import datetime

        sub_date = datetime.fromtimestamp(channel.subscribe)
        subscribe_str = f"✅ Активна до {sub_date.strftime('%d.%m.%Y')}"
    else:
        subscribe_str = "❌ Не активна"

    # Получаем статусы бота и помощника
    try:
        # 1. Проверка прав основного бота (Постинг)
        from aiogram.enums import ChatMemberStatus

        bot_member = await call.bot.get_chat_member(channel.chat_id, call.bot.id)

        bot_can_post = False
        if bot_member.status in [
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        ]:
            if hasattr(bot_member, "can_post_messages"):
                bot_can_post = bot_member.can_post_messages
            else:
                bot_can_post = True  # Если создатель или старое API

        status_bot_post = "✅" if bot_can_post else "❌"

        # 2. Находим привязанного помощника (МТПрото)
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        assistant_can_stats = False
        assistant_can_stories = False
        mt_client = None

        if client_row:
            assistant_can_stats = client_row[0].is_admin
            assistant_can_stories = client_row[0].can_post_stories
            mt_client = client_row[0].client

        status_assistant_stats = "✅" if assistant_can_stats else "❌"
        status_assistant_story = "✅" if assistant_can_stories else "❌"

        # Рассылка и Приветствие зависят от прав бота
        status_bot_mail = "✅" if bot_can_post else "❌"

        # Проверка приветственных сообщений в БД
        hello_msgs = await db.channel_bot_hello.get_hello_messages(
            channel.chat_id, active=True
        )
        status_welcome = "✅" if hello_msgs else "❌"

        # Если права помощника не полные и он назначен - запускаем фоновую проверку
        if mt_client and (not assistant_can_stats or not assistant_can_stories):
            asyncio.create_task(check_permissions_task(channel.chat_id))

        if mt_client:
            import html

            clean_alias = mt_client.alias.replace("👤", "").strip()
            assistant_name = (
                f"@{html.escape(clean_alias)}"
                if " " not in clean_alias
                else html.escape(clean_alias)
            )
            assistant_desc = "<i>Сбор статистики и публикация историй</i>"
            assistant_header = (
                f"🤖 <b>Помощник:</b> {assistant_name}\n{assistant_desc}\n"
            )
        else:
            assistant_header = "🤖 <b>Помощник:</b> Не назначен\n"

    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}", exc_info=True)
        status_bot_post = "❓"
        status_assistant_stats = "❓"
        status_assistant_story = "❓"
        status_bot_mail = "❓"
        status_welcome = "❓"
        assistant_header = "🤖 <b>Помощник:</b> Ошибка получения данных\n"

    info_text = (
        f"📺 <b>Информация о канале</b>\n\n"
        f"🏷 <b>Название:</b> {channel.title}\n"
        f"👑 <b>Владелец:</b> {creator_name}\n"
        f"👥 <b>Подписчиков:</b> {members_count}\n"
        f"📅 <b>Добавлен:</b> {created_str}\n"
        f"💎 <b>Подписка:</b> {subscribe_str}\n\n"
        f"🛠 <b>Редакторы:</b>\n{editors_str}\n\n"
        f"📡 <b>Статус бота NOVA:</b>\n"
        f"├ 📝 Постинг: {status_bot_post}\n"
        f"├ 📨 Рассылка: {status_bot_mail}\n"
        f"└ 👋 Приветствие: {status_welcome}\n\n"
        f"{assistant_header}"
        f"├ 📊 Статистика: {status_assistant_stats}\n"
        f"└ 📸 Истории: {status_assistant_story}"
    )

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text=info_text,
            reply_markup=keyboards.manage_channel("ManageChannelPost"),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            raise e


@safe_handler(
    "Постинг: выбор канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Выбор канала для управления или добавления."""
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        channels = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(channels=channels, remover=int(temp[2]))
        )

    if temp[1] == "cancel":
        await call.message.delete()
        # Возврат в меню настроек (профиль)
        return await call.message.answer(
            text("start_profile_text"),
            reply_markup=keyboards.profile_menu(),
            parse_mode="HTML",
        )

    if temp[1] == "add":
        await state.set_state(AddChannel.waiting_for_channel)

        # Удаляем старое сообщение
        await call.message.delete()

        from config import Config

        # Отправляем текстовую инструкцию
        return await call.message.answer(
            text=text("channels:add:text").format(Config.BOT_USERNAME),
            reply_markup=keyboards.add_channel(),
        )

    # Сохранение ID канала в состояние или передача через callback
    channel_id = int(temp[1])
    # Сохранение в FSM для обновления
    await state.update_data(current_channel_id=channel_id)

    await render_channel_info(call, state, channel_id)


@safe_handler(
    "Постинг: отмена канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel(call: types.CallbackQuery):
    """Отмена действий и возврат к списку каналов."""
    channels = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="posting"
    )
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
        ),
    )


@safe_handler(
    "Постинг: управление каналом"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def manage_channel(call: types.CallbackQuery, state: FSMContext):
    """Управление настройками канала (удаление, права, добавление помощника)."""
    temp = call.data.split("|")

    if temp[1] == "delete":
        return await call.answer(text("delete_channel"), show_alert=True)

    if temp[1] == "cancel":
        return await cancel(call)

    if temp[1] == "invite_assistant":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            await call.answer("Ошибка: выберите канал заново", show_alert=True)
            return await cancel(call)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer("Канал не найден", show_alert=True)
            return

        # Проверяем, есть ли уже права у помощника
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        # Получение клиента
        if not client_row or not client_row[0].client:
            await call.answer("❌ Нет назначенного помощника", show_alert=True)
            return

        mt_client = client_row[0].client
        session_path = Path(mt_client.session_path)

        if not session_path.exists():
            await call.answer("❌ Файл сессии не найден", show_alert=True)
            return

        await call.answer("⏳ Создаю ссылку и добавляю помощника...", show_alert=False)

        try:
            # 1. Создание пригласительной ссылки
            invite = await call.bot.create_chat_invite_link(
                chat_id=channel.chat_id,
                name="Nova Assistant",
                creates_join_request=False,
            )

            # 2. Процесс вступления
            success = False
            async with SessionManager(session_path) as manager:
                try:
                    success = await manager.join(invite.invite_link, max_attempts=5)
                    # Обновление юзернейма если возможно
                    me = await manager.me()
                    if me and me.username:
                        await db.mt_client.update_mt_client(
                            mt_client.id, alias=me.username
                        )
                        mt_client.alias = (
                            me.username
                        )  # Обновление локального объекта для отображения
                except Exception as e:
                    logger.error(f"Ошибка при вступлении в канал: {e}")

            # 3. Обработка результата
            if success:
                import html

                username = mt_client.alias.replace("@", "")  # Очистка на всякий случай

                msg = (
                    f"✅ <b>Помощник успешно добавился в канал!</b>\n\n"
                    f"Теперь вам нужно выдать ему права администратора.\n\n"
                    f"📋 <b>Инструкция:</b>\n"
                    f"1. Зайдите в настройки канала -> Администраторы -> Добавить администратора.\n"
                    f"2. В поиске введите: @{html.escape(username)}\n"
                    f"3. Выберите этого пользователя и выдайте следующие права:\n"
                    f"   ✅ Публикация сообщений\n"
                    f"   ✅ Редактирование сообщений\n"
                    f"   ✅ Удаление сообщений\n"
                    f"   ✅ Публикация историй\n"
                    f"   ✅ Редактирование историй\n"
                    f"   ✅ Удаление историй\n\n"
                    f"После выдачи прав нажмите кнопку <b>«Проверить права помощника»</b>."
                )
                await call.message.edit_text(
                    text=msg,
                    parse_mode="HTML",
                    reply_markup=keyboards.manage_channel("ManageChannelPost"),
                )

            else:
                await call.answer(
                    "⚠️ Не удалось добавить помощника (5 попыток). Попробуйте позже.",
                    show_alert=True,
                )

        except Exception as e:
            logger.error(f"Ошибка при приглашении помощника: {e}")
            await call.answer(
                f"❌ Ошибка: удостоверьтесь, что бот - админ ({e})", show_alert=True
            )
        return

    if temp[1] == "check_permissions":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            # Попытка восстановления состояния
            await call.answer("Ошибка: выберите канал заново", show_alert=True)
            return await cancel(call)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer("Канал не найден", show_alert=True)
            return

        await call.answer("⏳ Проверяем права...", show_alert=False)

        # 1. Получение клиента
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            # Клиент не назначен? Попытка назначения.
            from main_bot.handlers.user.set_resource import set_channel_session

            await set_channel_session(channel.chat_id)
            # Повторное получение
            client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            await call.answer("❌ Ошибка: нет назначенного помощника", show_alert=True)
            return

        mt_client = client_row[0].client

        if not mt_client:
            await call.answer("❌ Ошибка клиента", show_alert=True)
            return

        # 2. Проверка прав
        session_path = Path(mt_client.session_path)
        if not session_path.exists():
            await call.answer("❌ Ошибка сессии помощника", show_alert=True)
            return

        async with SessionManager(session_path) as manager:
            perms = await manager.check_permissions(channel.chat_id)
            logger.info(
                f"Ручная проверка прав для {channel.title} ({channel.chat_id}): {perms}"
            )

        if perms.get("error"):
            error_code = perms["error"]
            if error_code == "USER_NOT_PARTICIPANT":
                error_msg = "Помощник не найден в участниках канала. Статус сброшен."
                # 3. Обновление БД (Сброс)
                await db.mt_client_channel.set_membership(
                    client_id=mt_client.id,
                    channel_id=channel.chat_id,
                    is_member=False,
                    is_admin=False,
                    can_post_stories=False,
                    last_joined_at=int(time.time()),
                    preferred_for_stats=client_row[0].preferred_for_stats,
                )
                await render_channel_info(call, state, channel.chat_id)
            else:
                error_msg = f"Ошибка: {error_code}"

            await call.answer(f"❌ {error_msg}", show_alert=True)
            return

        # 3. Обновление БД
        is_admin = perms.get("is_admin", False)
        can_post = perms.get("can_post_messages", False)
        can_stories = perms.get("can_post_stories", False)
        logger.info(
            f"Обновление прав: админ={is_admin}, постинг={can_post}, истории={can_stories}"
        )

        # Обновление алиаса клиента
        me = perms.get("me")
        if me and me.username:
            await db.mt_client.update_mt_client(mt_client.id, alias=me.username)

        await db.mt_client_channel.set_membership(
            client_id=mt_client.id,
            channel_id=channel.chat_id,
            is_member=perms.get("is_member", False),
            is_admin=is_admin,
            can_post_messages=can_post,
            can_post_stories=can_stories,
            last_joined_at=int(time.time()),
            preferred_for_stats=client_row[
                0
            ].preferred_for_stats,  # Сохранение существующего предпочтения
        )

        # 4. Обновление отображения
        await render_channel_info(call, state, channel.chat_id)

        if is_admin and (can_stories or not perms.get("can_post_stories")):
            # Уведомление об успехе
            await call.answer("✅ Права успешно обновлены!", show_alert=True)
        else:
            await call.answer(
                "⚠️ Не все права выданы. Проверьте настройки админа.", show_alert=True
            )


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePostChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelPost")
    router.callback_query.register(
        manage_channel, F.data.split("|")[0] == "ManageChannelPost"
    )
    return router
