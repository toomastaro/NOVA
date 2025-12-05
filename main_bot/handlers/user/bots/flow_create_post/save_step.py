"""
Модуль подтверждения и сохранения поста для ботов.

Содержит логику:
- Подтверждение публикации поста
- Сохранение поста в БД с выбранными ботами и временем
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.database.types import Status
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots

logger = logging.getLogger(__name__)


async def accept(call: types.CallbackQuery, state: FSMContext):
    """
    Подтверждение и сохранение поста для ботов.
    
    Действия:
    - cancel: возврат к предыдущему шагу
    - send_time: сохранение с отложенной публикацией
    - public: немедленная публикация
    """
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == "cancel":
        if send_time:
            await state.update_data(send_time=None)
            message_text = text("manage:post_bot:new:send_time").format(
                *data.get("day_values")
            )
            reply_markup = keyboards.choice_send_time_bot_post(day=data.get("day"))
            await state.set_state(Bots.input_send_time)
        else:
            message_text = text("manage:post_bot:finish_params").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available")
            )
            reply_markup = keyboards.finish_bot_post_params(
                obj=post
            )

        if is_edit:
            message_text = text("bot:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_bot_post(
                post=data.get("post")
            )

        return await call.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )

    date_values: tuple = data.get("date_values")
    kwargs = {}

    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    if temp[1] == "public":
        kwargs["status"] = Status.READY

    await db.update_bot_post(
        post_id=post.id,
        **kwargs
    )

    if send_time:
        message_text = text("manage:post_bot:success:date").format(
            *date_values,
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )
    else:
        message_text = text("manage:post_bot:success:public").format(
            "\\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )

    await state.clear()
    await call.message.delete()
    await call.message.answer(
        message_text,
        reply_markup=keyboards.create_finish(
            data="MenuBots"
        )
    )
