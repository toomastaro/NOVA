"""
Модуль финального сохранения поста для ботов.

Реализует:
- Подтверждение публикации (сразу или отложенно)
- Обновление статуса поста в БД
- Отправку черновика в канал бэкапа
"""

import logging
from datetime import datetime
from typing import Any, Dict, Union

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db_types import Status
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.states.user import Bots
from main_bot.handlers.user.bots.flow_create_post.media_step import (
    serialize_bot_post,
)
from utils.error_handler import safe_handler
from main_bot.utils.message_utils import answer_bot_post

logger = logging.getLogger(__name__)


class DictObj:
    """Вспомогательный класс для доступа к ключам словаря как к атрибутам."""

    def __init__(self, in_dict: dict):
        for key, val in in_dict.items():
            setattr(self, key, val)


def ensure_bot_post_obj(
    post: Union[BotPost, Dict[str, Any]],
) -> Union[BotPost, DictObj]:
    """
    Гарантирует, что post является объектом (или DictObj).
    """
    if isinstance(post, dict):
        return DictObj(post)
    return post


@safe_handler(
    "Боты: подтверждение создания поста"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def accept(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Финальное подтверждение создания поста.
    Либо публикует сразу, либо планирует отправку, либо возвращает к редактированию.

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

    post: BotPost = ensure_bot_post_obj(data.get("post"))

    if not post:
        await call.answer(text("keys_data_error"))
        await call.message.delete()
        return

    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
    objects = await db.channel.get_user_channels(
        call.from_user.id, from_array=[i.id for i in channels]
    )

    if temp[1] == "cancel":
        if send_time:
            await state.update_data(send_time=None)
            message_text = text("manage:post_bot:new:send_time")
            day_str = data.get("day")
            day = (
                datetime.fromisoformat(day_str) if isinstance(day_str, str) else day_str
            )
            reply_markup = keyboards.choice_send_time_bot_post(day=day)
            await state.set_state(Bots.input_send_time)
        else:
            message_text = text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen
                ),
                data.get("available"),
            )
            reply_markup = keyboards.finish_bot_post_params(obj=post)

        if is_edit:
            message_text = text("bot_post:content").format(
                text("no_label")
                if not post.delete_time
                else f"{int(post.delete_time / 3600)} {text('hours_short')}",
                data.get("send_date_values")[0],
                data.get("send_date_values")[1],
                data.get("send_date_values")[2],
                data.get("channel").get("title") if isinstance(data.get("channel"), dict) else data.get("channel").title,
            )
            reply_markup = keyboards.manage_remain_bot_post(
                post=ensure_bot_post_obj(data.get("post"))
            )

        await call.message.edit_text(message_text, reply_markup=reply_markup)
        return

    # Обработка кнопки "Изменить дату/время"
    if temp[1] == "change_time":
        await call.message.edit_text(
            text("manage:post_bot:new:send_time"), reply_markup=None
        )
        await state.set_state(Bots.input_send_time)
        return

    date_values: tuple = data.get("date_values")
    kwargs = {}

    # Обрабатываем оба варианта: send_time (запланировать) и public (разослать)
    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    elif temp[1] == "public":
        kwargs["status"] = Status.READY
    else:
        # Неизвестная команда
        return

    # Update bot post in DB
    post = await db.bot_post.update_bot_post(post_id=post.id, return_obj=True, **kwargs)
    await state.update_data(post=serialize_bot_post(post))
    post = ensure_bot_post_obj(serialize_bot_post(post))

    # --- ПРЕВЬЮ (Прямой рендеринг из БД) ---
    try:
        # Отправляем превью пользователю напрямую из данных поста
        await answer_bot_post(call.message, state, from_edit=True)
    except Exception as e:
        logger.error(f"Ошибка при генерации превью бот-поста {post.id}: {e}", exc_info=True)

    # После нажатия "Запланировать" показываем сообщение об успехе
    await state.clear()

    # Prepare detailed info for success messages
    delete_time_text = (
        f"{int(post.delete_time / 3600)} {text('hours_short')}"
        if post.delete_time
        else text("no_label")
    )

    channels_text = "\n".join(
        text("resource_title").format(obj.title)
        for obj in objects
        if obj.chat_id in chosen
    )

    subscribers_count = data.get("available", 0)

    if send_time:
        weekday, day, month, year, _time = date_values
        message_text = text("manage:post_bot:success:date").format(
            weekday,
            day,
            month,
            year,
            _time,
            subscribers_count,
            channels_text,
            delete_time_text,
        )
    else:
        current_date = datetime.now().strftime("%d.%m.%Y %H:%M")
        message_text = text("manage:post_bot:success:public").format(
            current_date, subscribers_count, channels_text, delete_time_text
        )

    await call.message.delete()
    await call.message.answer(
        message_text, reply_markup=keyboards.create_finish(data="MenuBots")
    )
    # Reload Main Menu (Reply) to ensure navigation is available
    await call.message.answer(text("main_menu_label"), reply_markup=Reply.menu())
