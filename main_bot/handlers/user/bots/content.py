"""
Модуль управления контент-планом ботов.

Включает:
- Просмотр календаря рассылок
- Навигацию по дням/месяцам
- Управление запланированными постами (просмотр, редактирование, удаление)
- Формирование отчетов по дням
"""

from datetime import datetime, timedelta
import logging

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.utils.backup_utils import send_to_backup
from main_bot.handlers.user.bots.bot_content import (
    serialize_channel,
    serialize_bot_post,
    get_days_with_bot_posts,
    ensure_bot_post_obj,
)
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler(
    "Боты: контент — выбор канала"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_channel(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор канала для просмотра контент-плана бота.
    Отображает календарь постов для выбранного канала.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
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

    day = datetime.today()
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


@safe_handler(
    "Боты: контент — выбор дня/поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_row_content(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор дня или навигация по календарю контента.
    Обрабатывает переключение дней, месяцев и показ списка постов.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
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
    show_more: bool = data.get("show_more")

    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (day_str or datetime.today())
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

    # Если нет бэкапа - создаем
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.bot_post.update_bot_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id,
            )
            post.backup_chat_id = backup_chat_id
            post.backup_message_id = backup_message_id

    # Показываем превью (через CopyMessage из бэкапа)
    post_message = None
    if post.backup_chat_id and post.backup_message_id:
        try:
            post_message = await call.bot.copy_message(
                chat_id=call.from_user.id,
                from_chat_id=post.backup_chat_id,
                message_id=post.backup_message_id,
                # Без reply_markup - показываем только контент поста
            )
        except Exception:
            # Fallback если копирование не удалось
            post_message = await answer_bot_post(call.message, state, from_edit=True)
    else:
        post_message = await answer_bot_post(call.message, state, from_edit=True)

    if post_message:
        await state.update_data(
            post_message=post_message.model_dump(mode="json"),
            post=serialize_bot_post(post),  # Обновляем объект
        )

    if post.status in [Status.FINISH, Status.ERROR]:
        await call.message.delete()
        await call.message.answer(
            text("report_finished").format(
                post.success_send,
                post.error_send,
                "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} ч.",
                datetime.fromtimestamp(post.start_timestamp).strftime("%d.%m.%Y %H:%M"),
                datetime.fromtimestamp(post.end_timestamp).strftime("%d.%m.%Y %H:%M"),
                (await call.bot.get_chat(post.admin_id)).username,
            ),
            reply_markup=keyboards.back(data="ManageRemainBotPost|cancel"),
        )
        return

    await call.message.delete()

    # Получаем username автора
    try:
        author = (await call.bot.get_chat(post.admin_id)).username or "Неизвестно"
    except Exception:
        author = "Неизвестно"

    await call.message.answer(
        text("bot_post:content").format(
            "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} час.",
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
            author,
        ),
        reply_markup=keyboards.manage_remain_bot_post(post=post),
    )


@safe_handler(
    "Боты: контент — список постов"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор конкретного поста из списка time objects.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    channel_data = data.get("channel")

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
        else (datetime.today())
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


@safe_handler(
    "Боты: контент — управление постом"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def manage_remain_post(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Управление запланированным постом.
    Поддерживает изменение клавиатуры или удаление поста.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    channel_data = data.get("channel")
    day_str = data.get("day")
    day = (
        datetime.fromisoformat(day_str)
        if isinstance(day_str, str)
        else (datetime.today())
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


@safe_handler(
    "Боты: контент — подтверждение удаления"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def accept_delete_row_content(
    call: types.CallbackQuery, state: FSMContext
) -> None:
    """
    Подтверждение удаления поста.
    Удаляет пост из базы данных и возвращает пользователя в календарь.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
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
            author = (await call.bot.get_chat(post.admin_id)).username or "Неизвестно"
        except Exception:
            author = "Неизвестно"

        send_date = datetime.fromtimestamp(post.send_time or post.start_timestamp)

        await call.message.edit_text(
            text("bot_post:content").format(
                "Нет"
                if not post.delete_time
                else f"{int(post.delete_time / 3600)} час.",
                send_date.day,
                text("month").get(str(send_date.month)),
                send_date.year,
                author,
            ),
            reply_markup=keyboards.manage_remain_bot_post(post=post),
        )
        return

    if temp[1] == "accept":
        await db.bot_post.delete_bot_post(post.id)
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
    Регистрация роутеров управления контентом ботов.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
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
