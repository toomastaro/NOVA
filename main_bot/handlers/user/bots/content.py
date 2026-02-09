"""
Модуль управления контент-планом ботов.

Включает:
- Просмотр календаря рассылок
- Навигацию по дням/месяцам
- Управление запланированными постами (просмотр, редактирование, удаление)
- Формирование отчетов по дням
"""

import logging
import html
import re
import time
from datetime import datetime, timedelta, timezone

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.handlers.user.common_content import serialize_channel
from main_bot.handlers.user.bots.bot_content import (
    serialize_bot_post,
    get_days_with_bot_posts,
    ensure_bot_post_obj,
)
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Боты: выбор канала")
async def choice_channel(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора канала для просмотра контент-плана.

    Входы:
        call (types.CallbackQuery): Данные колбэка.
        state (FSMContext): Машина состояний.
    """
    logger.info("Вызов выбора канала для ботов")
    temp = call.data.split("|")

    if temp[1] in ["next", "back"]:
        channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
        objects = await db.channel.get_user_channels(
            call.from_user.id, from_array=[i.id for i in channels]
        )

        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=objects, remover=int(temp[2]), data="ChoiceObjectContentBots"
            )
        )
        return

    if temp[1] == "cancel":
        await call.message.delete()
        await start_bots(call.message)
        return

    bot_id = int(temp[1])
    channel = await db.channel.get_channel_by_chat_id(bot_id)

    day = datetime.now(timezone.utc)
    posts = await db.bot_post.get_bot_posts(channel.chat_id, day)
    days_with_posts = await get_days_with_bot_posts(
        channel.chat_id, day.year, day.month
    )
    day_values = (
        day.day,
        text("month").get(str(day.month)),
        day.year,
    )

    await state.update_data(
        channel=serialize_channel(channel),
        day=day.isoformat(),
        day_values=day_values,
        show_more=False,
    )

    await call.message.delete()
    await call.message.answer(
        text("bot:content").format(
            channel.title,
            *day_values,
            text("no_content") if not posts else text("has_content").format(len(posts)),
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts, day=day, data="ContentBotPost", days_with_posts=days_with_posts
        ),
    )


@safe_handler("Боты: выбор дня или поста")
async def choice_row_content(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик навигации по календарю и выбора рассылки.

    Входы:
        call (types.CallbackQuery): Данные колбэка.
        state (FSMContext): Машина состояний.
    """
    logger.info("Выбор строки контента в ботах: %s", call.data)
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    if temp[1] == "cancel":
        await call.message.delete()
        await show_content(call.message)
        return

    channel_data = data.get("channel")
    if not channel_data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return
    show_more: bool = data.get("show_more")

    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (day_str or datetime.now(timezone.utc))
    )

    if temp[1] in [
        "next_day",
        "next_month",
        "back_day",
        "back_month",
        "choice_day",
        "show_more",
    ]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], "%Y-%m-%d")
        elif temp[1] == "show_more":
            show_more = not show_more
        else:
            day = day - timedelta(days=int(temp[2]))

        posts = await db.bot_post.get_bot_posts(channel_data["chat_id"], day)
        days_with_posts = await get_days_with_bot_posts(
            channel_data["chat_id"], day.year, day.month
        )
        day_values = (
            day.day,
            text("month").get(str(day.month)),
            day.year,
        )

        await state.update_data(
            day=day.isoformat(), day_values=day_values, show_more=show_more
        )

        await call.message.edit_text(
            text("bot:content").format(
                *day_values,
                channel_data["title"],
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentBotPost",
                days_with_posts=days_with_posts,
            ),
        )
        return

    if temp[1] == "show_all":
        all_posts = await db.bot_post.get_bot_posts(channel_data["chat_id"])
        # Показываем только запланированные рассылки
        posts = [post for post in all_posts if post.status == Status.PENDING]
        await call.message.edit_text(
            text("bot:show_all:content").format(
                channel_data["title"],
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_time_objects(
                objects=posts, data="ContentBotPost"
            ),
        )
        return

    if temp[1] == "...":
        await call.answer()
        return

    post_id = int(temp[1])
    post = await db.bot_post.get_bot_post(post_id)

    send_date = datetime.fromtimestamp(post.send_time or post.start_timestamp)
    send_date_values = (
        send_date.day,
        text("month").get(str(send_date.month)),
        send_date.year,
    )
    await state.update_data(
        post=serialize_bot_post(post), send_date_values=send_date_values, is_edit=True
    )

    # Показываем превью напрямую из БД
    post_message = await answer_bot_post(call.message, state, from_edit=True)

    if post_message:
        await state.update_data(
            post_message={"message_id": post_message.message_id},
            post=serialize_bot_post(post),  # Обновляем объект
        )

    if post.status == Status.DELETED:
        await call.message.delete()
        send_date = datetime.fromtimestamp(post.send_time or post.start_timestamp)
        deleted_date = (
            datetime.fromtimestamp(post.deleted_at) if post.deleted_at else send_date
        )

        try:
            author_obj = await call.bot.get_chat(post.admin_id)
            author = author_obj.username or "Неизвестно"
        except Exception as e:
            logger.warning("Не удалось получить автора: %s", e)
            author = "Неизвестно"

        options = post.message
        message_text = (
            options.get("text") or options.get("caption") or text("media_label")
        )

        # Очистка от HTML-тегов перед обрезкой для предотвращения битых тегов
        message_text = re.sub(r"<[^>]+>", "", message_text)

        if len(message_text) > 30:
            message_text = message_text[:27] + "..."

        logger.info("Отправка отчета об удаленной рассылке %s", post.id)
        await call.message.answer(
            text("bot_post:deleted:report").format(
                send_date.strftime("%d.%m.%Y %H:%M"),
                deleted_date.strftime("%d.%m.%Y %H:%M"),
                html.escape(author),
                html.escape(message_text),
            ),
            reply_markup=keyboards.back(data="ManageRemainBotPost|cancel"),
        )
        return

    if post.status in [Status.FINISH, Status.ERROR]:
        logger.info("Отображение завершенной рассылки %s", post.id)
        await call.message.delete()

        try:
            admin_chat = await call.bot.get_chat(post.admin_id)
            admin_name = admin_chat.username or text("unknown")
        except Exception as e:
            logger.warning("Ошибка получения админа: %s", e)
            admin_name = text("unknown")

        await call.message.answer(
            text("report_finished_bot").format(
                post.success_send,
                post.error_send,
                (
                    text("no_label")
                    if not post.delete_time
                    else f"{int(post.delete_time / 3600)} {text('hours_short')}"
                ),
                (
                    datetime.fromtimestamp(post.start_timestamp).strftime(
                        "%d.%m.%Y %H:%M"
                    )
                    if post.start_timestamp
                    else text("unknown")
                ),
                (
                    datetime.fromtimestamp(post.end_timestamp).strftime(
                        "%d.%m.%Y %H:%M"
                    )
                    if post.end_timestamp
                    else text("unknown")
                ),
                html.escape(admin_name),
            ),
            reply_markup=keyboards.back(data="ManageRemainBotPost|cancel"),
        )
        return

    await call.message.delete()

    # Получаем username автора
    try:
        author_chat = await call.bot.get_chat(post.admin_id)
        author = author_chat.username or text("unknown")
    except Exception as e:
        logger.warning("Не удалось получить автора: %s", e)
        author = text("unknown")

    logger.info("Отображение управления постом %s", post.id)
    await call.message.answer(
        text("bot_post:content").format(
            (
                text("no_label")
                if not post.delete_time
                else f"{int(post.delete_time / 3600)} {text('hours_short')}"
            ),
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
            html.escape(author),
        ),
        reply_markup=keyboards.manage_remain_bot_post(post=post),
    )


@safe_handler("Боты: список постов")
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик выбора конкретного поста из списка.

    Входы:
        call (types.CallbackQuery): Данные колбэка.
        state (FSMContext): Машина состояний.
    """
    logger.info("Список постов в ботах: %s", call.data)
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    channel_data = data.get("channel")
    if not channel_data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    if temp[1] in ["next", "back"]:
        posts = await db.bot_post.get_bot_posts(channel_data["chat_id"])
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(
                objects=posts, remover=int(temp[2]), data="ChoiceTimeObjectContentBots"
            )
        )
        return

    show_more: bool = data.get("show_more")
    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (datetime.now(timezone.utc))
    )

    if temp[1] == "cancel":
        posts = await db.bot_post.get_bot_posts(channel_data["chat_id"], day)
        await call.message.edit_text(
            text("bot:content").format(
                *data.get("day_values"),
                channel_data["title"],
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentBotPost",
                days_with_posts=await get_days_with_bot_posts(
                    channel_data["chat_id"], day.year, day.month
                ),
            ),
        )


@safe_handler("Боты: управление постом")
async def manage_remain_post(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработчик управления запланированной рассылкой.

    Входы:
        call (types.CallbackQuery): Данные колбэка.
        state (FSMContext): Машина состояний.
    """
    logger.info("Управление постом в ботах: %s", call.data)
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    channel_data = data.get("channel")
    if not channel_data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (datetime.now(timezone.utc))
    )

    if temp[1] == "cancel":
        posts = await db.bot_post.get_bot_posts(channel_data["chat_id"], day)

        # Удаляем превью поста
        post_message = data.get("post_message")
        if post_message:
            try:
                msg_id = (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else (
                        post_message.message_id
                        if hasattr(post_message, "message_id")
                        else None
                    )
                )
                if msg_id:
                    await call.bot.delete_message(
                        chat_id=call.from_user.id, message_id=msg_id
                    )
            except Exception:
                pass

        await call.message.edit_text(
            text("bot:content").format(
                channel_data["title"],
                *data.get("day_values"),
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentBotPost",
                days_with_posts=await get_days_with_bot_posts(
                    channel_data["chat_id"], day.year, day.month
                ),
            ),
        )
        return

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeleteBotPost"
            ),
        )
        return

    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")
        if post_message:
            try:
                msg_id = (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else (
                        post_message.message_id
                        if hasattr(post_message, "message_id")
                        else None
                    )
                )
                if msg_id:
                    await call.bot.edit_message_reply_markup(
                        chat_id=call.from_user.id,
                        message_id=msg_id,
                        reply_markup=keyboards.manage_bot_post(
                            post=ensure_bot_post_obj(data.get("post")),
                            is_edit=data.get("is_edit"),
                        ),
                    )
            except Exception as e:
                logger.error(f"Ошибка редактирования клавиатуры: {e}")


@safe_handler("Боты: удаление поста")
async def accept_delete_row_content(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Обработчик подтверждения и выполнения удаления поста.

    Входы:
        call (types.CallbackQuery): Данные колбэка.
        state (FSMContext): Машина состояний.
    """
    logger.info("Удаление поста в ботах: %s", call.data)
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    day = data.get("day")
    day_values = data.get("day_values")
    # send_date_values = data.get("send_date_values")
    channel_data = data.get("channel")
    post = ensure_bot_post_obj(data.get("post"))

    if temp[1] == "cancel":
        # Получаем username автора
        try:
            author_chat = await call.bot.get_chat(post.admin_id)
            author = author_chat.username or "Неизвестно"
        except Exception as e:
            logger.warning("Не удалось получить автора: %s", e)
            author = "Неизвестно"

        send_date = datetime.fromtimestamp(post.send_time or post.start_timestamp)

        await call.message.edit_text(
            text("bot_post:content").format(
                (
                    text("no_label")
                    if not post.delete_time
                    else f"{int(post.delete_time / 3600)} {text('hours_short')}"
                ),
                send_date.day,
                text("month").get(str(send_date.month)),
                send_date.year,
                html.escape(author),
            ),
            reply_markup=keyboards.manage_remain_bot_post(post=post),
        )
        return

    if temp[1] == "accept":
        logger.info("Выполнение мягкого удаления рассылки %s", post.id)
        # Софт-удаление вместо полного удаления из БД, чтобы планировщик мог зачистить сообщения в TG
        await db.bot_post.update_bot_post(
            post_id=post.id, status=Status.DELETED, deleted_at=int(time.time())
        )
        posts = await db.bot_post.get_bot_posts(channel_data["chat_id"], day)

        # Удаляем превью поста
        post_message = data.get("post_message")
        if post_message:
            try:
                msg_id = (
                    post_message.get("message_id")
                    if isinstance(post_message, dict)
                    else (
                        post_message.message_id
                        if hasattr(post_message, "message_id")
                        else None
                    )
                )
                if msg_id:
                    await call.bot.delete_message(
                        chat_id=call.from_user.id, message_id=msg_id
                    )
            except Exception:
                pass

        await call.message.edit_text(
            text("bot:content").format(
                channel_data["title"],
                *day_values,
                (
                    text("no_content")
                    if not posts
                    else text("has_content").format(len(posts))
                ),
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentBotPost",
                days_with_posts=await get_days_with_bot_posts(
                    channel_data["chat_id"], day.year, day.month
                ),
            ),
        )


def get_router() -> Router:
    """
    Регистрация обработчиков для управления контентом ботов.

    Выходы:
        Router: Объект роутера с правилами.
    """
    router = Router()
    router.callback_query.register(
        choice_channel, F.data.split("|")[0] == "ChoiceObjectContentBots"
    )
    router.callback_query.register(
        choice_row_content, F.data.split("|")[0] == "ContentBotPost"
    )
    router.callback_query.register(
        choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentBots"
    )
    router.callback_query.register(
        manage_remain_post, F.data.split("|")[0] == "ManageRemainBotPost"
    )
    router.callback_query.register(
        accept_delete_row_content, F.data.split("|")[0] == "AcceptDeleteBotPost"
    )
    return router
