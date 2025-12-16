"""
Модуль обработки медиа и управления stories.

Содержит логику:
- Получение медиа для stories (фото/видео)
- Управление stories (отмена, переход к каналам, параметры)
- Редактирование параметров stories
"""

import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.story.model import Story
from main_bot.handlers.user.menu import start_stories
from main_bot.handlers.user.stories.menu import show_create_post
from main_bot.utils.message_utils import answer_story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Media, StoryOptions
from main_bot.keyboards import keyboards
from main_bot.states.user import Stories
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Stories Cancel Message")
async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    """Отмена создания stories - очистка состояния и возврат в меню."""
    await state.clear()
    await call.message.delete()
    await start_stories(call.message)


@safe_handler("Stories Get Message")
async def get_message(message: types.Message, state: FSMContext):
    """
    Получение медиа для создания stories.
    Обрабатывает фото и видео с опциональным текстом.
    """
    # Получаем выбранные каналы из state
    data = await state.get_data()
    chosen = data.get("chosen", [])

    message_text_length = len(message.caption or "")
    if message_text_length > 1024:
        return await message.answer(text("error_length_text"))

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    story_options = StoryOptions(**dump_message)
    if message_text_length:
        if story_options.caption:
            story_options.caption = message.html_text

    # Проверка на наличие медиа (сторис не может быть только текстом)
    if not story_options.photo and not story_options.video:
        return await message.answer(text("require_media"))

    # Создаем story с выбранными каналами
    post = await db.story.add_story(
        return_obj=True,
        chat_ids=chosen,
        admin_id=message.from_user.id,
        story_options=story_options.model_dump(),
    )

    # Отправляем в бэкап канал
    try:
        from main_bot.utils.backup_utils import send_to_backup
        backup_chat_id, backup_message_id = await send_to_backup(post)
        
        if backup_chat_id and backup_message_id:
            post = await db.story.update_story(
                post_id=post.id,
                return_obj=True,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id
            )
    except Exception as e:
        logger.error(f"Ошибка при отправке сторис в бэкап: {e}", exc_info=True)

    # Преобразуем объект post в dict для сохранения в FSM
    post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    await state.clear()
    await state.update_data(post=post_dict, chosen=chosen)

    # Показываем превью истории с возможностью редактирования
    await answer_story(message, state)


@safe_handler("Stories Manage Post")
async def manage_post(call: types.CallbackQuery, state: FSMContext):
    """Управление stories - обработка различных действий."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    
    from main_bot.keyboards.posting import ensure_obj
    post: Story = ensure_obj(data.get("post"))
    is_edit: bool = data.get("is_edit")

    if temp[1] == "cancel":
        if is_edit:
            post_message = await answer_story(call.message, state, from_edit=True)
            await state.update_data(post_message=post_message, show_more=False)
            await call.message.delete()
            return await call.message.answer(
                text("story:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_story(post=post),
            )

        await db.story.delete_story(post.id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    if temp[1] == "next":
        if is_edit:
            post_message = await answer_story(call.message, state, from_edit=True)
            await state.update_data(post_message=post_message, show_more=False)
            await call.message.delete()
            return await call.message.answer(
                text("story:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_story(post=post),
            )

        # Fix: Proceed to Finish Params instead of going back to Channel Selection
        from main_bot.handlers.user.stories.flow_create_post.schedule_step import (
            get_story_report_text,
        )

        chosen = data.get("chosen", post.chat_ids)
        objects = await db.channel.get_user_channels(
            user_id=call.from_user.id, sort_by="stories"
        )

        await call.message.delete()
        return await call.message.answer(
            text("manage:story:finish_params").format(
                len(chosen), await get_story_report_text(chosen, objects)
            ),
            reply_markup=keyboards.finish_params(obj=post, data="FinishStoriesParams"),
        )

    if temp[1] in ["noforwards", "pinned"]:
        story_options = StoryOptions(**post.story_options)

        if temp[1] == "noforwards":
            story_options.noforwards = not story_options.noforwards
        if temp[1] == "pinned":
            story_options.pinned = not story_options.pinned

        post = await db.story.update_story(
            post_id=post.id,
            return_obj=True,
            story_options=story_options.model_dump(),
        )
        # Преобразуем в dict перед сохранением
        post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
        await state.update_data(post=post_dict)

        await call.message.delete()
        return await answer_story(call.message, state)

    await state.update_data(param=temp[1])

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media"]:
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1], data="ParamCancelStories"
            ),
        )
        await state.set_state(Stories.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)


@safe_handler("Stories Cancel Value")
async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования параметра или удаление значения."""
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    if temp[1] == "delete":
        param = data.get("param")
        from main_bot.keyboards.posting import ensure_obj
        post = ensure_obj(data.get("post"))
        message_options = StoryOptions(**post.story_options)

        if param == "text":
            message_options.caption = None
        if param == "media":
            # Нельзя удалить медиа, так как сторис обязана содержать фото или видео
            return await call.answer(text("require_media"), show_alert=True)

        none_list = [
            message_options.photo is None,
            message_options.video is None,
        ]
        if False not in none_list:
            # Если (каким-то чудом) медиа нет - удаляем сторис
            await state.clear()
            await call.message.delete()
            await db.story.delete_story(post.id)
            return await show_create_post(call.message, state)

        kwargs = {"story_options": message_options.model_dump()}

        post = await db.story.update_story(
            post_id=post.id, return_obj=True, **kwargs
        )
        # Преобразуем в dict
        post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
        await state.update_data(post=post_dict)
        data = await state.get_data()

    await state.clear()
    await state.update_data(data)

    await call.message.delete()
    await answer_story(call.message, state)


@safe_handler("Stories Get Value")
async def get_value(message: types.Message, state: FSMContext):
    """Получение нового значения параметра от пользователя."""
    data = await state.get_data()
    param = data.get("param")

    if param == "media" and message.text:
        return await message.answer(text("error_value"))
    if param != "media" and not message.text:
        return await message.answer(text("error_value"))

    from main_bot.keyboards.posting import ensure_obj
    post = ensure_obj(data.get("post"))
    message_options = StoryOptions(**post.story_options)

    if param == "text":
        if message_options.photo or message_options.video:
            message_options.caption = message.html_text


    if param == "media":
        if message.photo:
            message_options.photo = Media(file_id=message.photo[-1].file_id)
        if message.video:
            message_options.video = Media(file_id=message.video.file_id)

    kwargs = {"story_options": message_options.model_dump()}

    post = await db.story.update_story(post_id=post.id, return_obj=True, **kwargs)

    # Преобразуем объект post в dict для сохранения в FSM
    post_dict = {col.name: getattr(post, col.name) for col in post.__table__.columns}
    
    await state.clear()
    data["post"] = post_dict
    await state.update_data(data)

    await message.bot.delete_message(message.chat.id, data.get("input_msg_id"))
    await answer_story(message, state)
