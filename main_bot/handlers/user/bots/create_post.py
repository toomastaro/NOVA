import time
from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db import db
from main_bot.database.types import Status
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_create_post, show_choice_channel
from main_bot.utils.functions import answer_bot_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Media, MessageOptionsHello
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import Bots


async def set_folder_content(resource_id, chosen, chosen_folders):
    folder = await db.get_folder_by_id(
        folder_id=resource_id
    )
    is_append = resource_id not in chosen_folders

    if is_append:
        chosen_folders.append(resource_id)
    else:
        chosen_folders.remove(resource_id)

    for chat_id in folder.content:
        chat_id = int(chat_id)

        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            return "subscribe", ""

        if is_append:
            if chat_id in chosen:
                continue
            chosen.append(chat_id)
        else:
            if chat_id not in chosen:
                continue
            chosen.remove(chat_id)

    return chosen, chosen_folders


async def choice_bots(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")

    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(
                text('error_min_choice')
            )

        await call.message.delete()
        return await show_create_post(call.message, state)

    folders = await db.get_folders(
        user_id=call.from_user.id,
    )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_bots(call.message)

    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                data="ChoicePostBots"
            )
        )

    if temp[1] == "choice_all":
        if len(chosen) == len(objects) and len(chosen_folders) == len(folders):
            chosen.clear()
            chosen_folders.clear()
        else:
            extend_list = [i.chat_id for i in objects if i.chat_id not in chosen and i.subscribe]
            if not extend_list:
                return await call.answer(
                    text("error_sub_all:bots")
                )

            chosen.extend(extend_list)
            if folders:
                for folder in folders:
                    sub_channels = []
                    for chat_id in folder.content:
                        user_bot = await db.get_channel_by_chat_id(int(chat_id))

                        if not user_bot.subscribe:
                            continue

                        sub_channels.append(int(chat_id))

                    if len(sub_channels) == len(folder.content):
                        chosen_folders.append(folder.id)

            chosen = list(set(chosen))

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])

        if temp[3] == 'channel':
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                user_bot = await db.get_channel_by_chat_id(resource_id)
                if not user_bot.subscribe:
                    return await call.answer(
                        text("error_sub_channel:bots")
                    )

                chosen.append(resource_id)
        else:
            temp_chosen, temp_chosen_folders = await set_folder_content(
                resource_id=resource_id,
                chosen=chosen,
                chosen_folders=chosen_folders
            )
            if temp_chosen == "subscribe":
                return await call.answer(
                    text("error_sub_channel_folder:bots")
                )

    available = 0
    for cs in channels:
        if cs.id in chosen:
            user_bot = await db.get_bot_by_id(cs.bot_id)
            other_db = Database()
            other_db.schema = user_bot.schema

            users = await other_db.get_users(cs.id)
            available += len(users)

    await state.update_data(
        chosen=chosen,
        chosen_folders=chosen_folders,
        available=available
    )

    await call.message.edit_text(
        text("choice_bots:post").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            available
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=int(temp[2]),
            data="ChoicePostBots"
        )
    )


async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    await show_choice_channel(call.message, state)


async def get_message(message: types.Message, state: FSMContext):
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
                "\n".join(
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


async def finish_params(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)

    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    if temp[1] == 'cancel':
        await call.message.delete()
        return await answer_bot_post(call.message, state)

    if temp[1] == "report":
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            report=not post.report
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(
                obj=post
            )
        )

    if temp[1] == "text_with_name":
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            text_with_name=not post.text_with_name
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_bot_post_params(
                obj=post
            )
        )

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time_bot_post()
        )

    if temp[1] == "send_time":
        day = datetime.today()
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values
        )

        await call.message.edit_text(
            text("manage:post_bot:new:send_time").format(
                *day_values
            ),
            reply_markup=keyboards.choice_send_time_bot_post(
                day=day,
            )
        )
        await state.set_state(Bots.input_send_time)

    if temp[1] == "public":
        await call.message.edit_text(
            text("manage:post_bot:accept:public").format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
            ),
            reply_markup=keyboards.accept_public(
                data="AcceptBotPost"
            )
        )


async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: BotPost = data.get("post")
    available: int = data.get("available")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    if post.delete_time != delete_time:
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            delete_time=delete_time
        )
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_post(
                post=post
            )
        )

    chosen: list = data.get("chosen")
    channels = await db.get_bot_channels(call.from_user.id)
    objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

    await call.message.edit_text(
        text("manage:post_bot:finish_params").format(
            len(chosen),
            "\n".join(
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


async def send_time_inline(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    temp = call.data.split("|")

    if temp[1] == "cancel":
        await state.clear()
        await state.update_data(data)

        is_edit: bool = data.get("is_edit")
        if is_edit:
            return await call.message.edit_text(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_bot_post(
                    post=data.get("post")
                )
            )

        chosen: list = data.get("chosen")
        channels = await db.get_bot_channels(call.from_user.id)
        objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

        return await call.message.edit_text(
            text("manage:post_bot:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                data.get("available")
            ),
            reply_markup=keyboards.finish_bot_post_params(
                obj=data.get('post')
            )
        )

    day: datetime = data.get("day")

    if temp[1] in ['next_day', 'next_month', 'back_day', 'back_month', "choice_day", "show_more"]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], '%Y-%m-%d')
        else:
            day = day - timedelta(days=int(temp[2]))

        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
        )

        return await call.message.edit_text(
            text("manage:post_bot:new:send_time").format(
                *day_values
            ),
            reply_markup=keyboards.choice_send_time_bot_post(
                day=day,
            )
        )


async def get_send_time(message: types.Message, state: FSMContext):
    input_date = message.text.strip()
    parts = input_date.split()
    data = await state.get_data()

    try:
        if len(parts) == 2 and len(parts[0].split('.')) == 3:
            date = datetime.strptime(input_date, "%H:%M %d.%m.%Y")

        elif len(parts) == 2 and len(parts[0].split('.')) == 2:
            year = datetime.now().year
            date = datetime.strptime(f"{parts[1]} {parts[0]}.{year}", "%H:%M %d.%m.%Y")

        elif len(parts) == 1:
            day = data.get("day", datetime.now())
            today = day.strftime("%d.%m.%Y")
            date = datetime.strptime(f"{parts[0]} {today}", "%H:%M %d.%m.%Y")
        else:
            raise ValueError("Invalid format")

        send_time = time.mktime(date.timetuple())

    except Exception as e:
        print(e)
        return await message.answer(
            text("error_value")
        )

    if time.time() > send_time:
        return await message.answer(
            text("error_time_value")
        )

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: BotPost = data.get('post')

    if is_edit:
        post = await db.update_bot_post(
            post_id=post.id,
            return_obj=True,
            send_time=send_time
        )
        send_date = datetime.fromtimestamp(post.send_time)
        send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)

        await state.clear()
        data['send_date_values'] = send_date_values
        await state.update_data(data)

        return await message.answer(
            text("bot_post:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_bot_post(
                post=post
            )
        )

    weekday = text("weekdays")[str(date.weekday())]
    month = text("month")[str(date.month)]
    day = date.day
    year = date.year
    _time = date.strftime('%H:%M')
    date_values = (weekday, day, month, year, _time,)

    await state.update_data(
        send_time=send_time,
        date_values=date_values
    )
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    chosen: list = data.get('chosen')

    channels = await db.get_bot_channels(message.from_user.id)
    objects = await db.get_user_channels(message.from_user.id, from_array=[i.id for i in channels])

    await message.answer(
        text("manage:post_bot:accept:date").format(
            *date_values,
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.accept_date(
            data="AcceptBotPost"
        )
    )


async def accept(call: types.CallbackQuery, state: FSMContext):
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
                "\n".join(
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
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )
    else:
        message_text = text("manage:post_bot:success:public").format(
            "\n".join(
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


def hand_add():
    router = Router()
    # Choice
    router.callback_query.register(choice_bots, F.data.split("|")[0] == "ChoicePostBots")

    # Manage
    router.message.register(get_message, Bots.input_message, F.text | F.photo | F.video | F.animation)
    router.callback_query.register(cancel_message, F.data.split("|")[0] == "InputBotPostCancel")
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManageBotPost")
    # Values
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamBotPostCancel")
    router.message.register(get_value, Bots.input_value, F.text | F.photo | F.video | F.animation)

    # Finish Params
    router.callback_query.register(finish_params, F.data.split("|")[0] == "FinishBotPostParams")
    router.callback_query.register(choice_delete_time, F.data.split("|")[0] == "GetDeleteTimeBotPost")
    router.callback_query.register(send_time_inline, F.data.split("|")[0] == "SendTimeBotPost")
    router.message.register(get_send_time, Bots.input_send_time, F.text)
    # Accept
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptBotPost")

    return router
