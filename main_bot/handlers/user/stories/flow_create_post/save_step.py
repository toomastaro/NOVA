"""
Модуль подтверждения и сохранения stories.

Содержит логику:
- Подтверждение публикации stories
- Сохранение stories в БД с выбранными каналами и временем
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.story.model import Story
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.states.user import Stories
from .schedule_step import get_story_report_text

logger = logging.getLogger(__name__)


async def accept(call: types.CallbackQuery, state: FSMContext):
    """
    Подтверждение и сохранение stories.
    
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

    post: Story = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )

    if temp[1] == "cancel":
        if send_time:
            await state.update_data(send_time=None)
            message_text = text("manage:story:new:send_time")
            reply_markup = keyboards.back(data="BackSendTimeStories")
            await state.set_state(Stories.input_send_time)
        else:
            message_text = text("manage:story:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.title) for obj in objects
                    if obj.chat_id in chosen[:10]
                )
            )
            reply_markup = keyboards.finish_params(
                obj=post,
                data="FinishStoriesParams"
            )

        if is_edit:
            message_text = text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_story(
                post=data.get("post")
            )

        return await call.message.edit_text(
            message_text,
            reply_markup=reply_markup
        )

    date_values: tuple = data.get("date_values")
    kwargs = {"chat_ids": chosen}

    if temp[1] == "send_time":
        kwargs["send_time"] = send_time or post.send_time
    if temp[1] == "public":
        kwargs["send_time"] = None

    await db.update_story(
        post_id=post.id,
        **kwargs
    )

    if send_time:
        message_text = text("manage:story:success:date").format(
            *date_values,
            await get_story_report_text(chosen, objects)
        )
    else:
        message_text = text("manage:story:success:public").format(
            "\n".join(
                text("resource_title").format(obj.title) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )

    await state.clear()
    await call.message.delete()
    await call.message.answer(
        message_text,
        reply_markup=keyboards.create_finish(
            data="MenuStories"
        )
    )
