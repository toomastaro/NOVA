import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path


from aiogram import types, F, Router
from aiogram.enums import ChatMemberStatus
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import AddChannel
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
from main_bot.utils.session_manager import SessionManager
from main_bot.utils import schedulers, background
from main_bot.database.db_types import FolderType
from main_bot.utils.schedulers import (
    schedule_channel_job,
    update_channel_stats,
)
from utils.error_handler import safe_handler
from main_bot.utils.user_settings import get_user_view_mode, set_user_view_mode
from config import Config


logger = logging.getLogger(__name__)


@safe_handler(
    "Постинг: фоновая проверка прав"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def check_permissions_task(chat_id: int):
    """Фоновая задача для обновления прав помощника."""
    # Removed: from main_bot.utils.session_manager import SessionManager
    # Removed: from main_bot.utils.tg_utils import db

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
                "Статус помощника сброшен для %s (удален из участников)", chat_id
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
        creator_name = text("unknown")

    # Получаем количество подписчиков
    try:
        members_count = await call.bot.get_chat_member_count(channel.chat_id)
    except Exception:
        members_count = "N/A"

    # Форматируем дату добавления
    created_date = datetime.fromtimestamp(channel.created_timestamp)
    created_str = created_date.strftime("%d.%m.%Y %H:%M")

    now_ts = datetime.now(timezone.utc).timestamp()
    if channel.subscribe and channel.subscribe > now_ts:
        sub_date = datetime.fromtimestamp(channel.subscribe)
        subscribe_str = text("status_active_until").format(sub_date.strftime("%d.%m.%Y"))
    else:
        subscribe_str = text("status_inactive")

    # Получаем статусы бота и помощника
    try:
        # 1. Проверка прав основного бота (Постинг)
        bot_member = await call.bot.get_chat_member(channel.chat_id, call.bot.id)

        bot_can_post = False
        if bot_member.status in [
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.CREATOR,
        ]:
            if hasattr(bot_member, "can_post_messages"):
                bot_can_post = bot_member.can_post_messages
            else:
                bot_can_post = True

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
            assistant_desc = text("assistant_desc")
            assistant_header = text("assistant_label").format(assistant_name) + f"\n{assistant_desc}\n"
        else:
            assistant_header = text("assistant_not_assigned") + "\n"

    except Exception as e:
        logger.error(f"Ошибка получения статуса: {e}", exc_info=True)
        status_bot_post = "❓"
        status_assistant_stats = "❓"
        status_assistant_story = "❓"
        status_bot_mail = "❓"
        status_welcome = "❓"
        assistant_header = text("assistant_error_data") + "\n"

    is_admin = call.from_user.id in getattr(Config, "ADMINS", [])

    info_text = (
        f"{text('channel_info_title')}\n\n"
        f"{text('owner_label').format(creator_name)}\n"
        f"{text('subscribers_label').format(members_count)}\n"
        f"{text('added_label').format(created_str)}\n"
        f"{text('subscription_label').format(subscribe_str)}\n\n"
        f"{text('editors_label')}\n{editors_str}"
    )

    if is_admin:
        info_text += (
            f"\n\n{text('nova_bot_status_label')}\n"
            f"├ {text('posting_label').format(status_bot_post)}\n"
            f"├ {text('mailing_label').format(status_bot_mail)}\n"
            f"└ {text('welcome_label').format(status_welcome)}\n\n"
            f"{assistant_header}"
            f"├ {text('stats_label').format(status_assistant_stats)}\n"
            f"└ {text('stories_label').format(status_assistant_story)}"
        )

    try:
        await call.message.edit_text(
            text=info_text,
            reply_markup=keyboards.manage_channel(
                "ManageChannelPost", user_id=call.from_user.id
            ),
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
    data = await state.get_data()
    view_mode = data.get("channels_view_mode")
    if not view_mode:
        view_mode = await get_user_view_mode(call.from_user.id)
        # Синхронизируем состояние FSM при первом входе, если оно пустое
        await state.update_data(channels_view_mode=view_mode)
    
    current_folder_id = data.get("channels_folder_id")

    if temp[1] == "switch_view":
        new_mode = temp[2]
        await state.update_data(channels_view_mode=new_mode)
        await set_user_view_mode(call.from_user.id, new_mode)
        # Сбрасываем папку при переключении режима? Обычно да.
        await state.update_data(channels_folder_id=None)
        
        # Перерисовываем меню
        return await cancel(call, state)

    if temp[1] == "close_folder":
        await state.update_data(channels_folder_id=None)
        return await cancel(call, state)

    if temp[1] in ["next", "back"]:
        folders = await db.user_folder.get_folders(user_id=call.from_user.id, folder_type=FolderType.CHANNEL)
        if current_folder_id:
            folder = await db.user_folder.get_folder_by_id(current_folder_id)
            channels = await db.channel.get_user_channels(
                user_id=call.from_user.id, 
                from_array=[int(c) for c in folder.content] if folder and folder.content else [],
                sort_by="posting"
            )
        else:
            if view_mode == "folders":
                channels = await db.channel.get_user_channels_without_folders(user_id=call.from_user.id)
            else:
                channels = await db.channel.get_user_channels(
                    user_id=call.from_user.id, sort_by="posting"
                )

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(
                channels=channels,
                remover=int(temp[2]),
                folders=folders,
                view_mode=view_mode,
                is_inside_folder=bool(current_folder_id),
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        # Сбрасываем состояние папок при выходе
        await state.update_data(channels_folder_id=None)
        # Возврат в меню настроек (профиль)
        return await call.message.answer(
            text("start_profile_text"),
            reply_markup=keyboards.profile_menu(),
            parse_mode="HTML",
        )

    if temp[1] == "add":
        await state.set_state(AddChannel.waiting_for_channel)
        await call.message.delete()
        from config import Config
        return await call.message.answer(
            text=text("channels:add:text").format(Config.BOT_USERNAME),
            reply_markup=keyboards.add_channel(),
        )

    # Обработка выбора папки или канала
    if len(temp) > 3 and temp[3] == "folder":
        folder_id = int(temp[1])
        await state.update_data(channels_folder_id=folder_id)
        return await cancel(call, state)

    # Сохранение ID канала в состояние или передача через callback
    channel_id = int(temp[1])
    # Сохранение в FSM для обновления
    await state.update_data(current_channel_id=channel_id)

    await render_channel_info(call, state, channel_id)


@safe_handler(
    "Постинг: отмена канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel(call: types.CallbackQuery, state: FSMContext = None):
    """Отмена действий и возврат к списку каналов."""
    if state is None:
        from main_bot.handlers import dp
        state = dp.fsm.get_context(call.bot, call.message.chat.id, call.from_user.id)

    data = await state.get_data()
    view_mode = data.get("channels_view_mode")
    if not view_mode:
        view_mode = await get_user_view_mode(call.from_user.id)
    current_folder_id = data.get("channels_folder_id")

    folders = await db.user_folder.get_folders(user_id=call.from_user.id, folder_type=FolderType.CHANNEL)
    
    if current_folder_id:
        folder = await db.user_folder.get_folder_by_id(current_folder_id)
        channels = await db.channel.get_user_channels(
            user_id=call.from_user.id, 
            from_array=[int(c) for c in folder.content] if folder and folder.content else [],
            sort_by="posting"
        )
    else:
        if view_mode == "folders":
            channels = await db.channel.get_user_channels_without_folders(user_id=call.from_user.id)
        else:
            channels = await db.channel.get_user_channels(
                user_id=call.from_user.id, sort_by="posting"
            )

    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
            folders=folders,
            view_mode=view_mode,
            is_inside_folder=bool(current_folder_id),
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
        return await cancel(call, state)

    if temp[1] == "invite_assistant":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            await call.answer(text("error_choose_channel_again"), show_alert=True)
            return await cancel(call, state)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer(text("error_channel_not_found"), show_alert=True)
            return

        # Проверяем, есть ли уже права у помощника
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        # Получение клиента
        if not client_row or not client_row[0].client:
            await call.answer(text("error_no_assistant"), show_alert=True)
            return

        mt_client = client_row[0].client
        session_path = Path(mt_client.session_path)

        if not session_path.exists():
            await call.answer(text("error_session_not_found"), show_alert=True)
            return

        await call.answer(text("assistant_invite_started"), show_alert=False)

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

                msg = text("assistant_invite_success_msg").format(html.escape(username))
                await call.message.edit_text(
                    text=msg,
                    parse_mode="HTML",
                    reply_markup=keyboards.manage_channel(
                        "ManageChannelPost", user_id=call.from_user.id
                    ),
                )

            else:
                await call.answer(
                    text("error_invite_failed"),
                    show_alert=True,
                )

        except Exception as e:
            logger.error(f"Ошибка при приглашении помощника: {e}")
            await call.answer(
                text("error_bot_not_admin").format(e), show_alert=True
            )
        return

    if temp[1] == "check_permissions":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            # Попытка восстановления состояния
            await call.answer(text("error_choose_channel_again"), show_alert=True)
            return await cancel(call, state)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer(text("error_channel_not_found"), show_alert=True)
            return

        await call.answer(text("assistant_check_started"), show_alert=False)

        # 1. Получение клиента
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            # Клиент не назначен? Попытка назначения.
            from main_bot.utils.tg_utils import set_channel_session

            await set_channel_session(channel.chat_id)
            # Повторное получение
            client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            await call.answer(text("error_no_assistant"), show_alert=True)
            return

        mt_client = client_row[0].client

        if not mt_client:
            await call.answer("❌ Ошибка клиента", show_alert=True)
            return

        # 2. Проверка прав
        session_path = Path(mt_client.session_path)
        if not session_path.exists():
            await call.answer(text("error_session_not_found"), show_alert=True)
            return

        async with SessionManager(session_path) as manager:
            perms = await manager.check_permissions(channel.chat_id)
            logger.info(
                f"Ручная проверка прав для {channel.title} ({channel.chat_id}): {perms}"
            )

        if perms.get("error"):
            error_code = perms["error"]
            if error_code == "USER_NOT_PARTICIPANT":
                error_msg = text("assistant_not_participant")
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

        # 4. Проверка и регистрация в планировщике + немедленный сбор данных
        if is_admin and schedulers.scheduler_instance:
            job_id = f"channel_stats_{channel.chat_id}"
            if not schedulers.scheduler_instance.get_job(job_id):
                try:
                    schedule_channel_job(schedulers.scheduler_instance, channel)
                    logger.info(f"Задача статистики {job_id} успешно создана вручную.")
                except Exception as e:
                    logger.error(f"Не удалось создать задачу статистики вручную: {e}")

            # В любом случае запускаем немедленный сбор
            background.run_background_task(
                update_channel_stats(channel.chat_id),
                name=f"manual_stats_posting_{channel.chat_id}",
            )

        # 5. Обновление отображения
        await render_channel_info(call, state, channel.chat_id)

        if is_admin and (can_stories or not perms.get("can_post_stories")):
            # Уведомление об успехе
            await call.answer(text("assistant_perms_success"), show_alert=True)
        else:
            await call.answer(
                text("assistant_perms_warning"), show_alert=True
            )


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePostChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelPost")
    router.callback_query.register(
        manage_channel, F.data.split("|")[0] == "ManageChannelPost"
    )
    return router
