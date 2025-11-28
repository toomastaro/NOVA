import time
from datetime import datetime

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.types import FolderType
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_create_post
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import AddHide, Posting
from main_bot.utils.functions import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Hide, Media, MessageOptions, React


async def get_post_text(post: Post, send_date_values: tuple) -> str:
    if len(post.chat_ids) == 1:
        channel = await db.get_channel_by_chat_id(post.chat_ids[0])
        return text("post:content").format(
            *send_date_values,
            channel.emoji_id,
            channel.title,
        )
    return text("post:content:multi").format(
        *send_date_values,
        len(post.chat_ids),
    )


# Функция set_folder_content удалена - больше не нужна для batch-отправки
# Логика папок теперь обрабатывается в menu.py


async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await start_posting(call.message)


async def get_message(message: types.Message, state: FSMContext):
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(text("error_length_text"))

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptions(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    # Extract buttons from reply_markup if present
    buttons_text = None
    if message.reply_markup and hasattr(message.reply_markup, 'inline_keyboard'):
        button_rows = []
        for row in message.reply_markup.inline_keyboard:
            button_items = []
            for button in row:
                # Only extract URL buttons (text—url format)
                if button.url:
                    button_items.append(f"{button.text}—{button.url}")
            if button_items:
                button_rows.append('|'.join(button_items))

        if button_rows:
            buttons_text = '\n'.join(button_rows)

    data = await state.get_data()
    chosen_channels = data.get("chosen_channels")

    # Если каналы уже выбраны в batch-режиме, создаем пост и переходим к финальным настройкам
    if chosen_channels:
        chat_ids = chosen_channels

        post = await db.add_post(
            return_obj=True,
            chat_ids=chat_ids,
            admin_id=message.from_user.id,
            message_options=message_options.model_dump(),
            buttons=buttons_text,
        )

        await state.clear()
        await state.update_data(show_more=False, post=post, chosen=chat_ids)

        # Переходим сразу к финальным настройкам (опубликовать/отложить)
        objects = await db.get_user_channels(user_id=message.from_user.id, sort_by="posting")

        await message.answer(
            text("manage:post:finish_params").format(
                len(chat_ids),
                "\n".join(
                    text("resource_title").format(obj.emoji_id, obj.title)
                    for obj in objects
                    if obj.chat_id in chat_ids[:10]
                ),
            ),
            reply_markup=keyboards.finish_params(obj=post),
        )
    else:
        # Если каналы не выбраны, создаем пост без каналов и переходим к выбору
        post = await db.add_post(
            return_obj=True,
            chat_ids=[],
            admin_id=message.from_user.id,
            message_options=message_options.model_dump(),
            buttons=buttons_text,
        )

        await state.clear()
        await state.update_data(show_more=False, post=post, chosen=[])

        # Переходим к выбору каналов для batch-отправки
        # Получаем все каналы и папки каналов
        channels = await db.get_user_channels(user_id=message.from_user.id, sort_by="subscribe")
        folders = await db.get_folders(user_id=message.from_user.id, folder_type=FolderType.CHANNEL)

        # Определяем каналы, которые уже есть в папках
        folder_channel_ids = set()
        for folder in folders:
            for chat_id_str in folder.content:
                if chat_id_str.lstrip('-').isdigit():
                    folder_channel_ids.add(int(chat_id_str))

        # Каналы для корневого отображения
        root_channels = [c for c in channels if c.chat_id not in folder_channel_ids]

        await state.update_data(chosen=[], current_folder_id=None)

        await message.answer(
            text("choice_channels:post_new").format(
                len(channels),
                "📁 " + ", ".join(f.title for f in folders[:3]) + ("..." if len(folders) > 3 else "") if folders else "Нет папок"
            ),
            reply_markup=keyboards.choice_channels_for_post(
                channels=root_channels,
                folders=folders,
                chosen=[],
                is_folder_view=False
            )
        )
        await state.set_state(Posting.choice_channel)


async def manage_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Post = data.get("post")
    is_edit: bool = data.get("is_edit")

    if temp[1] == "cancel":
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(post_message=post_message, show_more=False)
            await call.message.delete()
            return await call.message.answer(
                await get_post_text(post, data.get("send_date_values")),
                reply_markup=keyboards.manage_remain_post(post=post),
            )

        await db.delete_post(data.get("post").id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    if temp[1] == "show_more":
        await state.update_data(show_more=not data.get("show_more"))
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.manage_post(
                post=data.get("post"),
                show_more=not data.get("show_more"),
                is_edit=is_edit,
            )
        )

    if temp[1] in ["notification", "media_above", "has_spoiler"]:
        message_options = MessageOptions(**data.get("post").message_options)
        if temp[1] == "notification":
            message_options.disable_notification = (
                not message_options.disable_notification
            )

        if temp[1] in ["media_above", "has_spoiler"]:
            if (
                not message_options.photo
                and not message_options.video
                and not message_options.animation
            ):
                return await call.answer(text("require_media"), show_alert=True)

            if temp[1] == "has_spoiler":
                message_options.has_spoiler = not message_options.has_spoiler
            if temp[1] == "media_above":
                message_options.show_caption_above_media = (
                    not message_options.show_caption_above_media
                )

        post = await db.update_post(
            post_id=data.get("post").id,
            return_obj=True,
            message_options=message_options.model_dump(),
        )
        await state.update_data(post=post)

        await call.message.delete()
        return await answer_post(call.message, state)

    await state.update_data(param=temp[1])

    await call.message.delete()
    message_text = text(f"manage:post:new:{temp[1]}")

    if temp[1] in ["text", "media", "buttons", "reaction", "pin_time", "cpm_price"]:
        input_msg = await call.message.answer(
            message_text, reply_markup=keyboards.param_cancel(param=temp[1])
        )
        await state.set_state(Posting.input_value)
        await state.update_data(input_msg_id=input_msg.message_id)

    if temp[1] == "hide":
        await call.message.answer(
            message_text, reply_markup=keyboards.param_hide(post=data.get("post"))
        )


async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    if temp[1] == "delete":
        param = data.get("param")

        if param in ["text", "media"]:
            message_options = MessageOptions(**data.get("post").message_options)

            if param == "text":
                message_options.text = message_options.caption = None
            if param == "media":
                message_options.photo = message_options.video = (
                    message_options.animation
                ) = None

                if message_options.caption:
                    message_options.text = message_options.caption
                    message_options.caption = None

            none_list = [
                message_options.text is None,
                message_options.caption is None,
                message_options.photo is None,
                message_options.video is None,
                message_options.animation is None,
            ]
            if False not in none_list:
                await state.clear()
                await call.message.delete()
                await db.delete_post(data.get("post").id)
                return await show_create_post(call.message, state)

            kwargs = {"message_options": message_options.model_dump()}
        else:
            kwargs = {param: None}

        post = await db.update_post(
            post_id=data.get("post").id, return_obj=True, **kwargs
        )
        await state.update_data(post=post)
        data = await state.get_data()

    await state.clear()
    await state.update_data(data)

    await call.message.delete()
    await answer_post(call.message, state)


async def get_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    param = data.get("param")

    if param == "media" and message.text:
        return await message.answer(text("error_value"))
    if param != "media" and not message.text:
        return await message.answer(text("error_value"))

    post: Post = data.get("post")
    if param in ["text", "media"]:
        message_options = MessageOptions(**post.message_options)

        if param == "text":
            if (
                message_options.photo
                or message_options.video
                or message_options.animation
            ):
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

        kwargs = {"message_options": message_options.model_dump()}

    else:
        value = message.text

        if param in ["pin_time", "cpm_price"]:
            try:
                value = int(value)
                if param == "pin_time":
                    value *= 60

            except ValueError:
                return await message.answer(text("error_value"))
        else:
            if param == "buttons":
                post.buttons = value
            else:
                c = 0
                dict_react = {"rows": []}
                for a, row in enumerate(message.text.split("\n")):
                    reactions = []
                    for react in row.split("|"):
                        reactions.append({"id": c, "react": react, "users": []})
                        c += 1
                    dict_react["rows"].append({"id": a, "reactions": reactions})

                post.reaction = dict_react
                value = dict_react

            try:
                post: Post = data.get("post")
                check = await message.answer(
                    "...", reply_markup=keyboards.manage_post(post)
                )
                await check.delete()
            except (IndexError, TypeError):
                return await message.answer(text("error_value"))

        kwargs = {param: value}

    # Исправление: явно сохраняем кнопки при обновлении поста
    if 'buttons' not in kwargs:
        kwargs['buttons'] = post.buttons

    post = await db.update_post(post_id=post.id, return_obj=True, **kwargs)

    await state.clear()
    data["post"] = post
    await state.update_data(data)

    await message.bot.delete_message(message.chat.id, data.get("input_msg_id"))
    await answer_post(message, state)


async def add_hide_value(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    await call.message.delete()

    if temp[1] == "...":
        return await call.answer()

    if temp[1] == "add":
        await state.update_data(hide_step="button_name")
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide"),
        )
        await state.set_state(AddHide.button_name)


async def back_input_button_name(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    await state.clear()
    await state.update_data(data)
    await call.message.delete()

    hide_step = data.get("hide_step")
    temp = call.data.split("|")

    if len(temp) == 1 or hide_step == "button_name" or temp[1] == "cancel":
        return await call.message.answer(
            text("manage:post:new:hide"),
            reply_markup=keyboards.param_hide(post=data.get("post")),
        )
    if hide_step == "not_member":
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide"),
        )
        return await state.set_state(AddHide.button_name)

    if hide_step == "for_member":
        await call.message.answer(
            text("manage:post:add:param:hide:not_member"),
            reply_markup=keyboards.param_hide_back(),
        )
        return await state.set_state(AddHide.not_member_text)


async def get_button_name(message: types.Message, state: FSMContext):
    await state.update_data(hide_button_name=message.text, hide_step="not_member")

    await message.answer(
        text("manage:post:add:param:hide:not_member"),
        reply_markup=keyboards.param_hide_back(),
    )
    await state.set_state(AddHide.not_member_text)


async def get_not_member_text(message: types.Message, state: FSMContext):
    if len(message.text) > 200:
        return await message.answer(text("error_200_length_text"))

    await state.update_data(hide_not_member_text=message.text, hide_step="for_member")

    await message.answer(
        text("manage:post:add:param:hide:for_member"),
        reply_markup=keyboards.param_hide_back(),
    )
    await state.set_state(AddHide.for_member_text)


async def get_for_member_text(message: types.Message, state: FSMContext):
    if len(message.text) > 200:
        return await message.answer(text("error_200_length_text"))

    await state.update_data(hide_for_member_text=message.text)
    data = await state.get_data()
    post: Post = data.get("post")

    if post.hide is None:
        post.hide = []

    post.hide.append(
        {
            "id": len(post.hide) + 1,
            "button_name": data.get("hide_button_name"),
            "for_member": data.get("hide_for_member_text"),
            "not_member": data.get("hide_not_member_text"),
        }
    )

    post = await db.update_post(post_id=post.id, return_obj=True, hide=post.hide)

    await state.clear()
    await state.update_data(post=post, show_more=data.get("show_more"), param="hide")

    await message.answer(
        text("manage:post:new:hide"), reply_markup=keyboards.param_hide(post=post)
    )


# Функция choice_channels удалена - выбор каналов теперь происходит в menu.py
# с использованием новых клавиатур choice_channels_for_post для batch-отправки


async def finish_params(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    objects = await db.get_user_channels(user_id=call.from_user.id, sort_by="posting")

    if temp[1] == "cancel":
        # Исправление: кнопка "Назад" теперь возвращает к редактированию поста, а не к выбору каналов
        await call.message.delete()
        return await answer_post(call.message, state)

    if temp[1] == "report":
        post = await db.update_post(
            post_id=post.id, return_obj=True, report=not post.report
        )
        await state.update_data(post=post)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_params(obj=post)
        )

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time(),
        )

    if temp[1] == "send_time":
        await call.message.edit_text(
            text("manage:post:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimePost"),
        )
        await state.set_state(Posting.input_send_time)

    if temp[1] == "public":
        await call.message.edit_text(
            text("manage:post:accept:public").format(
                "\n".join(
                    text("resource_title").format(obj.emoji_id, obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                f"{int(post.delete_time / 3600)} ч."  # type: ignore
                if post.delete_time
                else text("manage:post:del_time:not"),
            ),
            reply_markup=keyboards.accept_public(),
        )


async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Post = data.get("post")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    if post.delete_time != delete_time:
        post = await db.update_post(
            post_id=post.id, return_obj=True, delete_time=delete_time
        )
        await state.update_data(post=post)
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            await get_post_text(post, data.get("send_date_values")),
            reply_markup=keyboards.manage_remain_post(post=post),
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(user_id=call.from_user.id, sort_by="posting")

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.emoji_id, obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
        ),
        reply_markup=keyboards.finish_params(obj=data.get("post")),
    )


async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            await get_post_text(data.get("post"), data.get("send_date_values")),
            reply_markup=keyboards.manage_remain_post(post=data.get("post")),
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(user_id=call.from_user.id, sort_by="posting")

    await call.message.edit_text(
        text("manage:post:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(obj.emoji_id, obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
        ),
        reply_markup=keyboards.finish_params(obj=data.get("post")),
    )


async def get_send_time(message: types.Message, state: FSMContext):
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        if len(parts) == 2 and len(parts[0].split(".")) == 3:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")

        elif len(parts) == 2 and len(parts[0].split(".")) == 2:
            year = datetime.now().year
            date = datetime.strptime(f"{parts[0]}.{year} {parts[1]}", "%d.%m.%Y %H:%M")

        elif len(parts) == 1:
            today = datetime.now().strftime("%d.%m.%Y")
            date = datetime.strptime(f"{today} {parts[0]}", "%d.%m.%Y %H:%M")

        else:
            raise ValueError("Invalid format")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        print(e)
        return await message.answer(text("error_value"))

    if time.time() > send_time:
        return await message.answer(text("error_time_value"))

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: Post = data.get("post")

    if is_edit:
        post = await db.update_post(
            post_id=post.id, return_obj=True, send_time=send_time
        )
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (
            send_date.day,
            text("month").get(str(send_date.month)),
            send_date.year,
        )

        await state.clear()
        data["send_date_values"] = send_date_values
        await state.update_data(data)

        return await message.answer(
            await get_post_text(post, send_date_values),
            reply_markup=keyboards.manage_remain_post(post=post),
        )

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

    objects = await db.get_user_channels(
        user_id=message.from_user.id, sort_by="posting"
    )

    await message.answer(
        text("manage:post:accept:date").format(
            *date_values,
            "\n".join(
                text("resource_title").format(obj.emoji_id, obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            f"{int(post.delete_time / 3600)} ч."  # type: ignore
            if post.delete_time
            else text("manage:post:del_time:not"),
        ),
        reply_markup=keyboards.accept_date(),
    )


async def accept(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text("keys_data_error"))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    objects = await db.get_user_channels(user_id=call.from_user.id, sort_by="posting")

    if temp[1] == "cancel":
        if send_time:
            await state.update_data(send_time=None)
            message_text = text("manage:post:new:send_time")
            reply_markup = keyboards.back(data="BackSendTimePost")
            await state.set_state(Posting.input_send_time)
        else:
            message_text = text("manage:post:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(obj.emoji_id, obj.title)
                    for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
            )
            reply_markup = keyboards.finish_params(obj=post)

        if is_edit:
            message_text = await get_post_text(post, data.get("send_date_values"))
            reply_markup = keyboards.manage_remain_post(post=data.get("post"))

        return await call.message.edit_text(message_text, reply_markup=reply_markup)

    date_values: tuple = data.get("date_values")
    kwargs = {"chat_ids": chosen}

    if temp[1] == "public":
        kwargs["send_time"] = None

    await db.update_post(post_id=post.id, **kwargs)

    if send_time:
        message_text = text("manage:post:success:date").format(
            *date_values,
            "\n".join(
                text("resource_title").format(obj.emoji_id, obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            ),
        )
    else:
        message_text = text("manage:post:success:public").format(
            "\n".join(
                text("resource_title").format(obj.emoji_id, obj.title)
                for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )

    await state.clear()
    await call.message.delete()
    await call.message.answer(message_text, reply_markup=keyboards.create_finish())


async def click_hide(call: types.CallbackQuery):
    temp = call.data.split("|")

    published_post = await db.get_published_post(
        chat_id=call.message.sender_chat.id,
        message_id=call.message.message_id,
    )
    if not published_post:
        return

    user = await call.bot.get_chat_member(
        chat_id=call.message.sender_chat.id, user_id=call.from_user.id
    )

    hide_model = Hide(hide=published_post.hide)
    for row_hide in hide_model.hide:
        if row_hide.id != int(temp[1]):
            continue

        await call.answer(
            row_hide.for_member if user.status != "left" else row_hide.not_member,
            show_alert=True,
        )


async def click_react(call: types.CallbackQuery):
    temp = call.data.split("|")

    published_post = await db.get_published_post(
        chat_id=call.message.sender_chat.id,
        message_id=call.message.message_id,
    )
    if not published_post:
        return

    react_model = React(rows=published_post.reaction.get("rows"))
    for react_row in react_model.rows:
        for react in react_row.reactions:
            if call.from_user.id in react.users and int(temp[1]) == react.id:
                return await call.answer("✅")

            if call.from_user.id in react.users:
                react.users.remove(call.from_user.id)
            if int(temp[1]) == react.id:
                react.users.append(call.from_user.id)

    post = await db.update_published_post(
        post_id=published_post.id, return_obj=True, reaction=react_model.model_dump()
    )
    await call.message.edit_reply_markup(reply_markup=keyboards.post_kb(post=post))


def hand_add():
    router = Router()
    # Manage
    router.message.register(
        get_message, Posting.input_message, F.text | F.photo | F.video | F.animation
    )
    router.callback_query.register(
        cancel_message, F.data.split("|")[0] == "InputPostCancel"
    )
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManagePost")
    # Values
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancel")
    router.message.register(
        get_value, Posting.input_value, F.text | F.photo | F.video | F.animation
    )
    # Hide
    router.callback_query.register(add_hide_value, F.data.split("|")[0] == "ParamHide")
    router.callback_query.register(
        back_input_button_name, F.data.split("|")[0] == "BackButtonHide"
    )
    router.message.register(get_button_name, AddHide.button_name, F.text)
    router.message.register(get_not_member_text, AddHide.not_member_text, F.text)
    router.message.register(get_for_member_text, AddHide.for_member_text, F.text)
    # Choice каналов перемещен в menu.py (batch-отправка)
    # Finish Params
    router.callback_query.register(
        finish_params, F.data.split("|")[0] == "FinishPostParams"
    )
    router.callback_query.register(
        choice_delete_time, F.data.split("|")[0] == "GetDeleteTimePost"
    )
    router.callback_query.register(
        cancel_send_time, F.data.split("|")[0] == "BackSendTimePost"
    )
    router.message.register(get_send_time, Posting.input_send_time, F.text)
    # Accept
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptPost")
    # Clicks
    router.callback_query.register(click_hide, F.data.split("|")[0] == "ClickHide")
    router.callback_query.register(click_react, F.data.split("|")[0] == "ClickReact")

    return router
