import time
from datetime import datetime

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.story.model import Story
from main_bot.handlers.user.menu import start_stories
from main_bot.handlers.user.stories.menu import show_create_post
from main_bot.utils.functions import answer_story
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import Media, StoryOptions
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import Stories


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


async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await start_stories(call.message)


async def get_message(message: types.Message, state: FSMContext):
    message_text_length = len(message.caption or "")
    if message_text_length > 1024:
        return await message.answer(
            text('error_length_text')
        )

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    story_options = StoryOptions(**dump_message)
    if message_text_length:
        if story_options.caption:
            story_options.caption = message.html_text

    post = await db.add_story(
        return_obj=True,
        chat_ids=[],
        admin_id=message.from_user.id,
        story_options=story_options.model_dump(),
    )

    await state.clear()
    await state.update_data(
        post=post
    )

    await answer_story(message, state)


async def manage_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Story = data.get('post')
    is_edit: bool = data.get('is_edit')

    if temp[1] == 'cancel':
        if is_edit:
            post_message = await answer_story(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("story:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_story(
                    post=post
                )
            )

        await db.delete_story(data.get('post').id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    if temp[1] == "next":
        if is_edit:
            post_message = await answer_story(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("story:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_story(
                    post=post
                )
            )

        objects = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="stories"
        )
        folders = await db.get_folders(
            user_id=call.from_user.id
        )
        await state.update_data(
            chosen=[],
            chosen_folders=[]
        )

        await call.message.delete()
        return await call.message.answer(
            text("choice_channels:story").format(
                0, ""
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=[],
                folders=folders,
                chosen_folders=[],
                data="ChoiceStoriesChannels"
            )
        )

    if temp[1] in ['noforwards', 'pinned']:
        story_options = StoryOptions(**data.get('post').story_options)

        if temp[1] == 'noforwards':
            story_options.noforwards = not story_options.noforwards
        if temp[1] == 'pinned':
            story_options.pinned = not story_options.pinned

        post = await db.update_story(
            post_id=data.get('post').id,
            return_obj=True,
            story_options=story_options.model_dump(),
        )
        await state.update_data(
            post=post
        )

        await call.message.delete()
        return await answer_story(call.message, state)

    await state.update_data(
        param=temp[1]
    )

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media"]:
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1],
                data="ParamCancelStories"
            )
        )
        await state.set_state(Stories.input_value)
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
        message_options = StoryOptions(**data.get('post').story_options)

        if param == "text":
            message_options.caption = None
        if param == "media":
            message_options.photo = message_options.video = None

        none_list = [
            message_options.photo is None,
            message_options.video is None,
        ]
        if False not in none_list:
            await state.clear()
            await call.message.delete()
            await db.delete_story(data.get('post').id)
            return await show_create_post(call.message, state)

        kwargs = {"story_options": message_options.model_dump()}

        post = await db.update_story(
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
    await answer_story(call.message, state)


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

    post: Story = data.get("post")
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

    post = await db.update_story(
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
    await answer_story(message, state)


async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    chosen_folders: list = data.get("chosen_folders")

    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )

    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(
                text('error_min_choice')
            )

        return await call.message.edit_text(
            text("manage:story:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=data.get('post'),
                data="FinishStoriesParams"
            )
        )

    folders = await db.get_folders(
        user_id=call.from_user.id
    )

    if temp[1] == "cancel":
        await call.message.delete()
        return await answer_story(call.message, state)

    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                data="ChoiceStoriesChannels"
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
                    text("error_sub_all")
                )

            chosen.extend(extend_list)
            if folders:
                for folder in folders:
                    sub_channels = []
                    for chat_id in folder.content:
                        channel = await db.get_channel_by_chat_id(int(chat_id))

                        if not channel.subscribe:
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
                channel = await db.get_channel_by_chat_id(resource_id)
                if not channel.subscribe:
                    return await call.answer(
                        text("error_sub_channel")
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
                    text("error_sub_channel_folder")
                )

    await state.update_data(
        chosen=chosen,
        chosen_folders=chosen_folders
    )
    await call.message.edit_text(
        text("choice_channels:story").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            chosen_folders=chosen_folders,
            remover=int(temp[2]),
            data="ChoiceStoriesChannels"
        )
    )


async def finish_params(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Story = data.get("post")
    options = StoryOptions(**post.story_options)

    chosen: list = data.get("chosen", post.chat_ids)
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )

    if temp[1] == 'cancel':
        chosen_folders: list = data.get("chosen_folders")
        folders = await db.get_folders(
            user_id=call.from_user.id
        )

        return await call.message.edit_text(
            text("choice_channels:story").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                )
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                chosen_folders=chosen_folders,
                data="ChoiceStoriesChannels"
            )
        )

    if temp[1] == "report":
        post = await db.update_story(
            post_id=post.id,
            return_obj=True,
            report=not post.report
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_params(
                obj=post,
                data="FinishStoriesParams"
            )
        )

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:story:new:delete_time"),
            reply_markup=keyboards.choice_delete_time_story()
        )

    if temp[1] == "send_time":
        await call.message.edit_text(
            text("manage:story:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimeStories")
        )
        await state.set_state(Stories.input_send_time)

    if temp[1] == "public":
        await call.message.edit_text(
            text("manage:story:accept:public").format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                f"{int(options.period / 3600)} ч."  # type: ignore
                if options.period else text("manage:post:del_time:not")
            ),
            reply_markup=keyboards.accept_public(
                data="AcceptStories"
            )
        )


async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Story = data.get("post")
    story_options = StoryOptions(**post.story_options)

    delete_time = story_options.period
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if story_options.period != delete_time:
        story_options.period = delete_time
        post = await db.update_story(
            post_id=post.id,
            return_obj=True,
            story_options=story_options.model_dump()
        )
        await state.update_data(
            post=post
        )
        data = await state.get_data()

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_story(
                post=post
            )
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )

    await call.message.edit_text(
        text("manage:story:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.finish_params(
            obj=data.get('post'),
            data="FinishStoriesParams"
        )
    )


async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await state.update_data(data)

    is_edit: bool = data.get("is_edit")
    if is_edit:
        return await call.message.edit_text(
            text("story:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_story(
                post=data.get("post")
            )
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="stories"
    )

    await call.message.edit_text(
        text("manage:story:finish_params").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        ),
        reply_markup=keyboards.finish_params(
            obj=data.get('post'),
            data="FinishStoriesParams"
        )
    )


async def get_send_time(message: types.Message, state: FSMContext):
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        if len(parts) == 2 and len(parts[0].split('.')) == 3:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")

        elif len(parts) == 2 and len(parts[0].split('.')) == 2:
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
        return await message.answer(
            text("error_value")
        )

    if time.time() > send_time:
        return await message.answer(
            text("error_time_value")
        )

    data = await state.get_data()
    is_edit: bool = data.get("is_edit")
    post: Story = data.get('post')
    options = StoryOptions(**post.story_options)

    if is_edit:
        post = await db.update_story(
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
            text("story:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_story(
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

    objects = await db.get_user_channels(
        user_id=message.from_user.id,
        sort_by="stories"
    )

    await message.answer(
        text("manage:story:accept:date").format(
            *date_values,
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            f"{int(options.period / 3600)} ч."  # type: ignore
            if options.period else text("manage:post:del_time:not")
        ),
        reply_markup=keyboards.accept_date(
            data="AcceptStories"
        )
    )


async def accept(call: types.CallbackQuery, state: FSMContext):
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
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
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
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            )
        )
    else:
        message_text = text("manage:story:success:public").format(
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
            data="MenuStories"
        )
    )


def hand_add():
    router = Router()
    # Manage
    router.message.register(get_message, Stories.input_message, F.photo | F.video)
    router.callback_query.register(cancel_message, F.data.split("|")[0] == "InputStoriesCancel")
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManageStory")
    # Values
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancelStories")
    router.message.register(get_value, Stories.input_value, F.text | F.photo | F.video)
    # Choice
    router.callback_query.register(choice_channels, F.data.split("|")[0] == "ChoiceStoriesChannels")
    # Finish Params
    router.callback_query.register(finish_params, F.data.split("|")[0] == "FinishStoriesParams")
    router.callback_query.register(choice_delete_time, F.data.split("|")[0] == "GetDeleteTimeStories")
    router.callback_query.register(cancel_send_time, F.data.split("|")[0] == "BackSendTimeStories")
    router.message.register(get_send_time, Stories.input_send_time, F.text)
    # # Accept
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptStories")
    return router
