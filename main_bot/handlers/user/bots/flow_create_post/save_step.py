"""
Модуль финального сохранения поста для ботов.

Реализует:
- Подтверждение публикации (сразу или отложенно)
- Обновление статуса поста в БД
- Отправку черновика в канал бэкапа
"""

import logging

from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db_types import Status
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots
from utils.error_handler import safe_handler
from main_bot.utils.backup_utils import send_to_backup, edit_backup_message

logger = logging.getLogger(__name__)


@safe_handler("Bots Accept")
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

    post: BotPost = data.get("post")

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
            reply_markup = keyboards.choice_send_time_bot_post(day=data.get("day"))
            await state.set_state(Bots.input_send_time)
        else:
            message_text = text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available"),
            )
            reply_markup = keyboards.finish_bot_post_params(obj=post)

        if is_edit:
            message_text = text("bot:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_bot_post(post=data.get("post"))

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
    await db.bot_post.update_bot_post(post_id=post.id, **kwargs)

    # Отправляем в backup если еще не отправлено
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.bot_post.update_bot_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id,
            )
            # Обновляем локальный объект
            post.backup_chat_id = backup_chat_id
            post.backup_message_id = backup_message_id
    else:
        # Если бэкап уже есть, обновляем его (для редактирования запланированных рассылок)
        await edit_backup_message(post)

    # После нажатия "Запланировать" показываем сообщение об успехе
    await state.clear()

    if send_time:
        weekday, day, month, year, _time = date_values
        message_text = text("manage:post_bot:success:date").format(
            weekday, day, month, year, _time
        )
    else:
        message_text = text("manage:post_bot:success:public").format(
            "\n".join(
                text("resource_title").format(obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )

    await call.message.delete()
    await call.message.answer(
        message_text, reply_markup=keyboards.create_finish(data="MenuBots")
    )
