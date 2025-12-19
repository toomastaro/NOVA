"""
Модуль настройки расписания и финальной конфигурации поста ботов.

Реализует:
- Управление временем отправки (календарь, ввод времени)
- Настройка параметров удаления поста
- Финальный обзор настроек (получатели, время, текст)
"""

import time
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, Union

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.handlers.user.bots.flow_create_post.media_step import (
    serialize_bot_post,
)
from main_bot.utils.message_utils import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


class DictObj:
    """Вспомогательный класс для доступа к ключам словаря как к атрибутам."""

    def __init__(self, in_dict: dict):
        for key, val in in_dict.items():
            setattr(self, key, val)

    def __getattr__(self, item):
        return None


def ensure_bot_post_obj(
    post: Union[BotPost, Dict[str, Any]],
) -> Union[BotPost, DictObj]:
    """
    Гарантирует, что post является объектом (или DictObj).
    """
    if isinstance(post, dict):
        return DictObj(post)
    return post


@safe_handler("Боты: финальные параметры поста")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def finish_params(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Экран финальной настройки параметров поста (отчет, удаление, время).

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
    chosen: list = data.get("chosen", post.chat_ids)

    channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
    objects = await db.channel.get_user_channels(
        call.from_user.id, from_array=[i.id for i in channels]
    )

    if temp[1] == "cancel":
        await call.message.delete()
        await answer_bot_post(call.message, state)
        return

    if temp[1] == "report":
        post = await db.bot_post.update_bot_post(
            post_id=post.id, return_obj=True, report=not post.report
        )
        await state.update_data(post=serialize_bot_post(post))
        await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(obj=post)
        )
        return

    if temp[1] == "text_with_name":
        post = await db.bot_post.update_bot_post(
            post_id=post.id, return_obj=True, text_with_name=not post.text_with_name
        )
        await state.update_data(post=serialize_bot_post(post))
        await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(obj=post)
        )
        return

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time_bot_post(),
        )
        return

    if temp[1] == "send_time":
        day = datetime.today()
        day_values = (
            day.day,
            text("month").get(str(day.month)),
            day.year,
        )

        await state.update_data(day=day, day_values=day_values)

        await call.message.edit_text(
            text("manage:post_bot:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimeBots"),
        )
        await state.set_state(Bots.input_send_time)
        return

    if temp[1] == "public":
        await call.message.edit_text(
            text("manage:post_bot:accept:public").format(
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
            ),
            reply_markup=keyboards.accept_bot_public(data="AcceptBotPost"),
        )


@safe_handler("Боты: выбор времени удаления")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice_delete_time(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Выбор времени автоудаления поста.

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
    available: int = data.get("available")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    if post.delete_time != delete_time:
        post = await db.bot_post.update_bot_post(
            post_id=post.id, return_obj=True, delete_time=delete_time
        )
        await state.update_data(post=serialize_bot_post(post))
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        send_date_values = data.get("send_date_values")
        username = "Unknown"
        try:
            username = (await call.bot.get_chat(post.admin_id)).username or "Unknown"
        except Exception:
            pass

        await call.message.edit_text(
            text("bot_post:content").format(
                (
                    "Нет"
                    if not post.delete_time
                    else f"{int(post.delete_time / 3600)} час."
                ),
                send_date_values[0],  # день
                send_date_values[1],  # месяц (уже строка)
                send_date_values[2],  # год
                username,
            ),
            reply_markup=keyboards.manage_remain_bot_post(post=post),
        )
        return

    chosen: list = data.get("chosen")
    channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
    objects = await db.channel.get_user_channels(
        call.from_user.id, from_array=[i.id for i in channels]
    )

    await call.message.edit_text(
        text("manage:post_bot:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            available,
        ),
        reply_markup=keyboards.finish_bot_post_params(obj=data.get("post")),
    )


@safe_handler("Боты: выбор времени отправки (инлайн)")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def send_time_inline(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработка навигации по календарю выбора даты отправки.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await state.clear()
        await state.update_data(data)

        is_edit: bool = data.get("is_edit")
        if is_edit:
            await call.message.edit_text(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title,
                ),
                reply_markup=keyboards.manage_remain_bot_post(post=data.get("post")),
            )
            return

        chosen: list = data.get("chosen")
        channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
        objects = await db.channel.get_user_channels(
            call.from_user.id, from_array=[i.id for i in channels]
        )

        await call.message.edit_text(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available"),
            ),
            reply_markup=keyboards.finish_bot_post_params(obj=data.get("post")),
        )
        return

    day: datetime = data.get("day")

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
        else:
            day = day - timedelta(days=int(temp[2]))

        day_values = (
            day.day,
            text("month").get(str(day.month)),
            day.year,
        )

        await state.update_data(
            day=day,
            day_values=day_values,
        )

        await call.message.edit_text(
            text("manage:post_bot:new:send_time"), reply_markup=None
        )


@safe_handler("Боты: получение времени отправки")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_send_time(message: types.Message, state: FSMContext) -> None:
    """
    Обработка ввода времени отправки (текстом).
    Парсит разные форматы (HH:MM, DD.MM HH:MM и др.).

    Аргументы:
        message (types.Message): Сообщение с временем.
        state (FSMContext): Контекст состояния.
    """
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        # Формат: DD.MM.YYYY HH:MM
        if len(parts) == 2 and len(parts[0].split(".")) == 3 and ":" in parts[1]:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")

        # Формат: HH:MM DD.MM.YYYY
        elif len(parts) == 2 and ":" in parts[0] and len(parts[1].split(".")) == 3:
            date = datetime.strptime(f"{parts[1]} {parts[0]}", "%d.%m.%Y %H:%M")

        # Формат: HH:MM DD.MM (без года)
        elif len(parts) == 2 and ":" in parts[0] and len(parts[1].split(".")) == 2:
            year = datetime.now().year
            date = datetime.strptime(f"{parts[1]}.{year} {parts[0]}", "%d.%m.%Y %H:%M")

        # Формат: HH:MM (только время, используем сегодняшнюю дату)
        elif len(parts) == 1 and ":" in parts[0]:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")

        else:
            raise ValueError("Неверный формат")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        logger.error(f"Ошибка парсинга времени отправки: {e}")
        await message.answer(text("error_value"))
        return

    if time.time() > send_time:
        await message.answer(text("error_time_value"))
        return

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: BotPost = ensure_bot_post_obj(data.get("post"))
    is_changing_time = (
        data.get("send_time") is not None
    )  # Проверяем, меняем ли мы время

    if is_edit:
        post = await db.bot_post.update_bot_post(
            post_id=post.id, return_obj=True, send_time=send_time
        )
        post = ensure_bot_post_obj(serialize_bot_post(post))
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
        )

        await state.update_data(send_date_values=send_date_values)
        data = await state.get_data()
        data["post"] = serialize_bot_post(post)
        await state.clear()
        await state.update_data(data)

        # Получаем username автора
        try:
            author = (await message.bot.get_chat(post.admin_id)).username or "Unknown"
        except Exception:
            author = "Unknown"

        await message.answer(
            text("bot_post:content").format(
                (
                    "Нет"
                    if not post.delete_time
                    else f"{int(post.delete_time / 3600)} час."
                ),
                send_date_values[0],  # день
                send_date_values[1],  # месяц
                send_date_values[2],  # год
                author,
            ),
            reply_markup=keyboards.manage_remain_bot_post(post=post),
        )
        return

    weekday = text("weekdays")[str(date.weekday())]
    month = text("month")[str(date.month)]
    day = date.day
    year = date.year
    _time = date.strftime("%H:%M")
    date_values = (
        weekday,
        day,
        month,
        year,
        _time,
    )

    await state.update_data(send_time=send_time, date_values=date_values)
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    chosen: list = data.get("chosen")

    channels = await db.channel_bot_settings.get_bot_channels(message.from_user.id)
    objects = await db.channel.get_user_channels(
        message.from_user.id, from_array=[i.id for i in channels]
    )

    # Если меняем время (уже было запланировано), сразу возвращаемся на экран "Готов к рассылке"
    if is_changing_time:
        await db.bot_post.update_bot_post(post_id=post.id, send_time=send_time)

        await message.answer(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available"),
            ),
            reply_markup=keyboards.finish_bot_post_params(obj=post),
        )
        return

    # Первый раз планируем - показываем экран с кнопкой "Запланировать"
    await message.answer(
        text("manage:post_bot:accept:date").format(
            _time,
            weekday,
            day,
            month,
            year,
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
        ),
        reply_markup=keyboards.accept_bot_date(data="AcceptBotPost"),
    )


@safe_handler("Боты: возврат к времени отправки")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def back_send_time(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Возврат из меню настройки времени к общим параметрам.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    post: BotPost = ensure_bot_post_obj(data.get("post"))
    chosen: list = (
        data.get("chosen") or post.chat_ids
    )  # Используем post.chat_ids если chosen None

    channels = await db.channel_bot_settings.get_bot_channels(call.from_user.id)
    objects = await db.channel.get_user_channels(
        call.from_user.id, from_array=[i.id for i in channels]
    )

    await call.message.edit_text(
        text("manage:post_bot:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            data.get("available") or 0,
        ),
        reply_markup=keyboards.finish_bot_post_params(obj=post),
    )
