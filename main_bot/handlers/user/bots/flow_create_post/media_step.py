"""
Модуль обработки медиа и управления постами для ботов.

Содержит логику:
- Получение сообщения для постов ботов
- Управление постами ботов
- Редактирование параметров
"""
import logging
from aiogram import types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.bot_post.model import BotPost
from main_bot.handlers.user.bots.menu import show_create_post, show_choice_channel
from main_bot.utils.message_utils import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Media, MessageOptionsHello
from main_bot.keyboards import keyboards
from main_bot.states.user import Bots

logger = logging.getLogger(__name__)


async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    """Отмена создания поста для ботов."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    await show_choice_channel(call.message, state)


async def get_message(message: types.Message, state: FSMContext):
    """Получение сообщения для создания поста для ботов."""
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(
            text('error_length_text')
        )

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptionsHello(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    data = await state.get_data()
    post = await db.add_bot_post(
        return_obj=True,
        chat_ids=data.get("chosen"),
        admin_id=message.from_user.id,
        message=message_options.model_dump(),
    )

    await state.clear()
    data["post"] = post
    await state.update_data(data)

    await answer_bot_post(message, state)


async def manage_post(call: types.CallbackQuery, state: FSMContext):
    """Управление постом для ботов."""
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get('post')
    is_edit: bool = data.get('is_edit')

    if temp[1] == 'cancel':
        if is_edit:
            post_message = await answer_bot_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
            )
            await call.message.delete()
            return await call.message.answer(
                text("bot_post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_bot_post(
                    post=post
                )
            )

        await db.delete_bot_post(data.get('post').id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    if temp[1] == "next":
        if is_edit:
            post_message = await answer_bot_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
            )
            await call.message.delete()
            return await call.message.answer(
                text("bot_post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_bot_post(
                    post=post
                )
            )

        chosen: list = data.get("chosen")
        available: int = data.get("available")
        channels = await db.get_bot_channels(call.from_user.id)
        objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

        await call.message.delete()
        return await call.message.answer(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                available
            ),
            reply_markup=keyboards.finish_bot_post_params(
                obj=data.get('post')
            )
        )

    await state.update_data(
        param=temp[1]
    )

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media", "buttons"]:
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1],
                data="ParamBotPostCancel"
            )
        )
        await state.set_state(Bots.input_value)
        await state.update_data(
            input_msg_id=input_msg.message_id
        )


async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    """Отмена редактирования параметра."""
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == 'delete':
        param = data.get('param')

        if param in ["text", "media", "buttons"]:
            message_options = MessageOptionsHello(**data.get('post').message)

            if param == "text":
                message_options.text = message_options.caption = None
            if param == "media":
                message_options.photo = message_options.video = message_options.animation = None

                if message_options.caption:
                    message_options.text = message_options.caption
                    message_options.caption = None
            if param == "buttons":
                message_options.reply_markup = None

            none_list = [
                message_options.text is None,
                message_options.caption is None,
                message_options.photo is None,
                message_options.video is None,
                message_options.animation is None,
            ]
            if False not in none_list:
                await state.clear()
                await state.update_data(**data)

                await call.message.delete()
                await db.delete_bot_post(data.get('post').id)
                return await show_create_post(call.message, state)

            kwargs = {"message": message_options.model_dump()}
        else:
            kwargs = {param: None}

        post = await db.update_bot_post(
            post_id=data.get('post').id,
            return_obj=True,
            **kwargs
        )
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    await state.clear()
    await state.update_data(data)

    await call.message.delete()
    await answer_bot_post(call.message, state)


async def get_value(message: types.Message, state: FSMContext):
    """Получение нового значения параметра."""
    data = await state.get_data()
    param = data.get('param')

    if param == "media" and message.text:
        return await message.answer(
            text("error_value")
        )
    if param != "media" and not message.text:
        return await message.answer(
            text("error_value")
        )

    post: BotPost = data.get("post")
    if param in ["text", "media", "buttons"]:
        message_options = MessageOptionsHello(**post.message)

        if param == "text":
            if message_options.photo or message_options.video or message_options.animation:
                message_options.caption = message.html_text
            else:
                message_options.text = message.html_text

        if param == "media":
            if message.photo:
                message_options.photo = Media(file_id=message.photo[-1].file_id)
            if message.video:
                message_options.video = Media(file_id=message.video.file_id)
            if message.animation:
                message_options.animation = Media(file_id=message.animation.file_id)

            if message_options.text:
                message_options.caption = message_options.text
                message_options.text = None
        if param == "buttons":
            try:
                reply_markup = keyboards.hello_kb(message.text)
                r = await message.answer('...', reply_markup=reply_markup)
                await r.delete()
            except Exception as e:
                print(e)
                return await message.answer(
                    text("error_input")
                )

            message_options.reply_markup = reply_markup

        kwargs = {"message": message_options.model_dump()}

    else:
        value = message.text
        if param == "buttons":
            post.buttons = value

            try:
                post: BotPost = data.get("post")
                check = await message.answer("...", reply_markup=keyboards.manage_bot_post(post))
                await check.delete()
            except (IndexError, TypeError):
                return await message.answer(
                    text("error_value")
                )

        kwargs = {param: value}

    post = await db.update_bot_post(
        post_id=post.id,
        return_obj=True,
        **kwargs
    )

    await state.clear()
    data['post'] = post
    await state.update_data(data)

    await message.bot.delete_message(
        message.chat.id,
        data.get("input_msg_id")
    )
    await answer_bot_post(message, state)
