from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from pathlib import Path
import time

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_stories
from main_bot.keyboards import keyboards
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
import logging
from utils.error_handler import safe_handler
from main_bot.utils.session_manager import SessionManager
from main_bot.states.user import AddChannel
from config import Config
from datetime import datetime
import asyncio
from main_bot.utils import schedulers, background
from main_bot.utils.schedulers import (
    schedule_channel_job,
    update_channel_stats,
)

logger = logging.getLogger(__name__)


async def render_channel_info(
    call: types.CallbackQuery, state: FSMContext, channel_id: int
):
    """Отображает информацию о канале (статистика, статус, редакторы) для историй."""
    channels = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )

    channel = await db.channel.get_channel_by_chat_id(channel_id)
    if not channel:
        return await call.message.edit_text(
            text=text("channels_text"),
            reply_markup=keyboards.channels(
                channels=channels, data="ChoiceStoriesChannel"
            ),
        )

    editors_str = await get_editors(call, channel.chat_id)

    # Получаем информацию о создателе
    try:
        creator = await call.bot.get_chat(channel.admin_id)
        creator_name = f"@{creator.username}" if creator.username else creator.full_name
    except Exception:
        creator_name = text("unknown")

    # Получаем количество подписчиков
    except Exception:
        pass

    # Форматируем дату добавления
    created_date = datetime.fromtimestamp(channel.created_timestamp)
    created_str = created_date.strftime("%d.%m.%Y в %H:%M")

    # Статус подписки
    if channel.subscribe:
        sub_date = datetime.fromtimestamp(channel.subscribe)
        subscribe_str = text("status_active_until").format(sub_date.strftime("%d.%m.%Y"))
    else:
        subscribe_str = text("status_inactive")

    # Получаем статус помощника
    try:
        # Находим привязанного клиента
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        can_post = False
        can_stories = False
        mt_client = None

        if client_row:
            if client_row[0].is_admin:
                pass

            can_post = client_row[0].is_admin
            can_stories = client_row[0].can_post_stories
            mt_client = client_row[0].client

        status_post = "✅" if can_post else "❌"
        status_story = "✅" if can_stories else "❌"
        # Рассылка зависит от логики постинга (TBD)
        status_mail = "❌"

        # Проверка приветственных сообщений
        hello_msgs = await db.channel_bot_hello.get_hello_messages(
            channel.chat_id, active=True
        )
        status_welcome = "✅" if hello_msgs else "❌"

        if mt_client:
            import html

            clean_alias = mt_client.alias.replace("👤", "").strip()
            if " " in clean_alias:
                assistant_name = html.escape(clean_alias)
            else:
                assistant_name = f"@{html.escape(clean_alias)}"
            assistant_desc = "<i>Назначенный помощник для этого канала</i>"
            assistant_header = f"🤖 <b>{text('assistant_status')}:</b> {assistant_name}\n{assistant_desc}\n"
        else:
            assistant_header = f"🤖 <b>{text('assistant_status')}:</b> {text('not_assigned')}\n"

    except Exception as e:
        logger.error(f"Ошибка получения статуса помощника: {e}")
        status_post = "❓"
        status_story = "❓"
        status_mail = "❓"
        status_welcome = "❓"
        assistant_header = f"🤖 <b>{text('assistant_status')}:</b> {text('error')}\n"

    is_admin = call.from_user.id in getattr(Config, "ADMINS", [])

    info_text = text("channel_info").format(
        channel.title,
        creator_name,
        created_str,
        subscribe_str,
        editors_str,
        Config.BOT_USERNAME,
    )

    if is_admin:
        info_text += (
            f"\n\n{assistant_header}"
            f"├ {text('posting_label').format(status_post)}\n"
            f"├ {text('stories_label').format(status_story)}\n"
            f"├ {text('mailing_label').format(status_mail)}\n"
            f"└ {text('welcome_label').format(status_welcome)}"
        )

    try:
        await call.message.edit_text(
            text=info_text,
            reply_markup=keyboards.manage_channel(
                "ManageChannelStories", user_id=call.from_user.id
            ),
            parse_mode="HTML",
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            await call.answer()
        else:
            raise e


@safe_handler("Сторис: выбор канала")
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Выбор канала для управления или добавления."""
    logger.info(f"Вызван хендлер выбора каналов сторис. Data: {call.data}")
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        logger.info(f"Обработка навигации сторис: {temp[1]}")
        channels = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="stories"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(
                channels=channels, remover=int(temp[2]), data="ChoiceStoriesChannel"
            )
        )

    if temp[1] == "cancel":
        logger.info("Отмена выбора сторис")
        await call.message.delete()
        return await start_stories(call.message)

    if temp[1] == "add":
        logger.info("Добавление нового канала сторис")
        await state.set_state(AddChannel.waiting_for_channel)

        # Удаляем старое сообщение
        await call.message.delete()

        # Отправляем текстовую инструкцию
        return await call.message.answer(
            text=text("channels:add:text").format(Config.BOT_USERNAME),
            reply_markup=keyboards.add_channel(
                bot_username=(await call.bot.get_me()).username,
                data="BackAddChannelStories",
            ),
        )

    # Сохраняем channel_id в состояние или передаем через callback
    channel_id = int(temp[1])
    logger.info(f"Выбран канал сторис: {channel_id}")

    # Сохраняем в FSM для обновления
    await state.update_data(current_channel_id=channel_id)

    await render_channel_info(call, state, channel_id)


@safe_handler("Сторис: отмена канала")
async def cancel(call: types.CallbackQuery):
    """Отмена действий и возврат к списку каналов."""
    channels = await db.channel.get_user_channels(
        user_id=call.from_user.id, sort_by="stories"
    )
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(channels=channels, data="ChoiceStoriesChannel"),
    )


@safe_handler("Сторис: управление каналом")
async def manage_channel(call: types.CallbackQuery, state: FSMContext):
    """Управление настройками канала (удаление, права, добавление помощника)."""
    logger.info(
        f"Вызван хендлер управления каналом (manage_channel). Data: {call.data}"
    )
    temp = call.data.split("|")

    if temp[1] == "delete":
        return await call.answer(text("delete_channel"), show_alert=True)

    if temp[1] == "cancel":
        return await cancel(call)

    if temp[1] == "favorite":
        # Не реализовано в stories?
        return await call.answer(text("function_in_development"), show_alert=True)

    if temp[1] == "invite_assistant":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            await call.answer("Ошибка: выберите канал заново", show_alert=True)
            return await cancel(call)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer(text("error_channel_not_found"), show_alert=True)
            return

        # Проверяем, есть ли уже права у помощника
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)
        if client_row:
            can_post = client_row[0].is_admin
            can_stories = client_row[0].can_post_stories

            # Если оба права уже есть - помощник уже добавлен
            if can_post and can_stories:
                await call.answer(
                    text("assistant_perms_success"),
                    show_alert=True,
                )
                # Возвращаемся на экран информации о канале
                return await render_channel_info(call, state, channel_id)

        # Получаем клиента
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
            # 1. Создаем ссылку приглашения
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
                    # Обновляем username, если возможно
                    me = await manager.me()
                    if me and me.username:
                        await db.mt_client.update_mt_client(
                            mt_client.id, alias=me.username
                        )
                        mt_client.alias = me.username
                except Exception as e:
                    logger.error(f"Join error: {e}")

            # 3. Обработка результата
            if success:
                import html

                username = mt_client.alias.replace("@", "")

                msg = text("assistant_invite_success_msg").format(html.escape(username))
                await call.message.edit_text(
                    text=msg,
                    parse_mode="HTML",
                    reply_markup=keyboards.manage_channel(
                        "ManageChannelStories", user_id=call.from_user.id
                    ),
                )

            else:
                await call.answer(
                    text("error_invite_failed"),
                    show_alert=True,
                )

        except Exception as e:
            logger.error(f"Invite assistant error: {e}")
            await call.answer(
                f"❌ Ошибка: удостоверьтесь, что бот - админ ({e})", show_alert=True
            )
        return

    if temp[1] == "check_permissions":
        data = await state.get_data()
        channel_id = data.get("current_channel_id")

        if not channel_id:
            await call.answer("Ошибка: выберите канал заново", show_alert=True)
            return await cancel(call)

        channel = await db.channel.get_channel_by_chat_id(channel_id)
        if not channel:
            await call.answer("Канал не найден", show_alert=True)
            return

        await call.answer(text("assistant_check_started"), show_alert=False)

        # 1. Получаем клиента
        client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            # Пытаемся назначить
            from main_bot.utils.tg_utils import set_channel_session

            await set_channel_session(channel.chat_id)
            client_row = await db.mt_client_channel.get_my_membership(channel.chat_id)

        if not client_row:
            await call.answer("❌ Ошибка: нет назначенного помощника", show_alert=True)
            return

        mt_client = client_row[0].client
        if not mt_client:
            await call.answer("❌ Ошибка клиента", show_alert=True)
            return

        # 2. Проверяем права
        session_path = Path(mt_client.session_path)
        if not session_path.exists():
            await call.answer("❌ Ошибка сессии помощника", show_alert=True)
            return

        async with SessionManager(session_path) as manager:
            perms = await manager.check_permissions(channel.chat_id)

        if perms.get("error"):
            error_code = perms["error"]
            if error_code == "USER_NOT_PARTICIPANT":
                error_msg = text("error_assistant_not_participant")
            else:
                error_msg = text("error_generic").format(error_code)

            await call.answer(f"❌ {error_msg}", show_alert=True)
            return

        # 3. Обновляем БД
        is_admin = perms.get("is_admin", False)
        can_stories = perms.get("can_post_stories", False)

        if perms.get("me") and perms.get("me").username:
            await db.mt_client.update_mt_client(
                mt_client.id, alias=perms.get("me").username
            )

        await db.mt_client_channel.set_membership(
            client_id=mt_client.id,
            channel_id=channel.chat_id,
            is_member=perms.get("is_member", False),
            is_admin=is_admin,
            can_post_stories=can_stories,
            last_joined_at=int(time.time()),
            preferred_for_stats=client_row[0].preferred_for_stats,
        )

        # 4. Проверка и регистрация в планировщике + немедленный сбор данных
        if is_admin and schedulers.scheduler_instance:
            job_id = f"channel_stats_{channel.chat_id}"
            if not schedulers.scheduler_instance.get_job(job_id):
                try:
                    schedule_channel_job(schedulers.scheduler_instance, channel)
                    logger.info(f"Задача статистики {job_id} успешно создана вручную (Stories).")
                except Exception as e:
                    logger.error(f"Не удалось создать задачу статистики вручную (Stories): {e}")

            # В любом случае запускаем немедленный сбор
            background.run_background_task(
                update_channel_stats(channel.chat_id),
                name=f"manual_stats_stories_{channel.chat_id}",
            )

        # 5. Обновляем вид
        await render_channel_info(call, state, channel_id)

        if is_admin and (can_stories or not perms.get("can_post_stories")):
            await call.answer(text("assistant_perms_success"), show_alert=True)
        else:
            await call.answer(
                text("assistant_perms_warning"), show_alert=True
            )


@safe_handler("Сторис: отмена добавления")
async def cancel_add_channel(call: types.CallbackQuery, state: FSMContext):
    """Возврат в меню сториз при отмене добавления канала."""

    await state.clear()
    await call.message.delete()
    await start_stories(call.message)


def get_router():
    router = Router()
    router.callback_query.register(
        choice, F.data.split("|")[0] == "ChoiceStoriesChannel"
    )
    router.callback_query.register(
        cancel_add_channel, F.data.split("|")[0] == "BackAddChannelStories"
    )
    router.callback_query.register(
        manage_channel, F.data.split("|")[0] == "ManageChannelStories"
    )
    return router
