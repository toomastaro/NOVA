import time
import logging
from datetime import datetime

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_create_post
from main_bot.utils.functions import answer_post
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions, Media, Hide, React
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting, AddHide
from main_bot.states.user import Posting, AddHide
from main_bot.utils.backup_utils import send_to_backup, edit_backup_message, update_live_messages

logger = logging.getLogger(__name__)




async def cancel_message(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    await start_posting(call.message)


async def get_message(message: types.Message, state: FSMContext):
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(
            text('error_length_text')
        )

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptions(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    buttons_str = None
    if message.reply_markup and message.reply_markup.inline_keyboard:
        rows = []
        for row in message.reply_markup.inline_keyboard:
            buttons = []
            for button in row:
                if button.url:
                    buttons.append(f"{button.text} — {button.url}")
            if buttons:
                rows.append("|".join(buttons))
        if rows:
            buttons_str = "\n".join(rows)

    post = await db.add_post(
        return_obj=True,
        chat_ids=[],
        admin_id=message.from_user.id,
        message_options=message_options.model_dump(),
        buttons=buttons_str
    )

    await state.clear()
    await state.update_data(
        show_more=False,
        post=post
    )

    await answer_post(message, state)


async def manage_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get('post')
    is_edit: bool = data.get('is_edit')

    if temp[1] == 'cancel':
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post,
                    is_published=data.get("is_published")
                )
            )

        await db.delete_post(data.get('post').id)
        await call.message.delete()
        return await show_create_post(call.message, state)

    if temp[1] == "next":
        if is_edit:
            post_message = await answer_post(call.message, state, from_edit=True)
            await state.update_data(
                post_message=post_message,
                show_more=False
            )
            await call.message.delete()
            return await call.message.answer(
                text("post:content").format(
                    *data.get("send_date_values"),
                    data.get("channel").emoji_id,
                    data.get("channel").title
                ),
                reply_markup=keyboards.manage_remain_post(
                    post=post,
                    is_published=data.get("is_published")
                )
            )

        objects = await db.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        folders = await db.get_folders(
            user_id=call.from_user.id
        )
        await state.update_data(
            chosen=[],
            current_folder_id=None
        )

        await call.message.delete()
        return await call.message.answer(
            text("choice_channels:post").format(
                0, ""
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=[],
                folders=folders
            )
        )

    if temp[1] == 'show_more':
        await state.update_data(
            show_more=not data.get('show_more')
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.manage_post(
                post=data.get('post'),
                show_more=not data.get('show_more'),
                is_edit=is_edit
            )
        )

    if temp[1] in ['notification', 'media_above', 'has_spoiler', 'pin_time']:
        message_options = MessageOptions(**data.get('post').message_options)
        if temp[1] == 'notification':
            message_options.disable_notification = not message_options.disable_notification

        if temp[1] in ['media_above', 'has_spoiler']:
            if not message_options.photo and not message_options.video and not message_options.animation:
                return await call.answer(text("require_media"), show_alert=True)

            if temp[1] == 'has_spoiler':
                message_options.has_spoiler = not message_options.has_spoiler
            if temp[1] == 'media_above':
                message_options.show_caption_above_media = not message_options.show_caption_above_media
        
        if temp[1] == 'pin_time':
            # Переключаем закреп: если был включен - выключаем, если выключен - включаем (True)
            new_pin_value = not post.pin_time if post.pin_time else True

        if data.get("is_published"):
            # Update all published posts with same post_id
            update_kwargs = {}
            if temp[1] == 'pin_time':
                update_kwargs['pin_time'] = new_pin_value
            else:
                update_kwargs['message_options'] = message_options.model_dump()
            
            await db.update_published_posts_by_post_id(
                post_id=post.post_id,
                **update_kwargs
            )
            # Fetch updated object (just one of them to keep in state)
            post = await db.get_published_post_by_id(post.id)
        else:
            update_kwargs = {}
            if temp[1] == 'pin_time':
                update_kwargs['pin_time'] = new_pin_value
            else:
                update_kwargs['message_options'] = message_options.model_dump()
            
            post = await db.update_post(
                post_id=data.get('post').id,
                return_obj=True,
                **update_kwargs
            )
        
        # Update backup message
        await edit_backup_message(post)
        
        # Update live messages if published
        if data.get("is_published"):
            await update_live_messages(post.post_id, message_options)

        await state.update_data(
            post=post
        )

        await call.message.delete()
        return await answer_post(call.message, state)

    await state.update_data(
        param=temp[1]
    )

    await call.message.delete()
    message_text = text("manage:post:new:{}".format(temp[1]))

    if temp[1] in ["text", "media", "buttons", "reaction"]:
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1]
            )
        )
        await state.set_state(Posting.input_value)
        await state.update_data(
            input_msg_id=input_msg.message_id
        )

    if temp[1] == "hide":
        await call.message.answer(
            message_text,
            reply_markup=keyboards.param_hide(
                post=data.get('post')
            )
        )


async def cancel_value(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == 'delete':
        param = data.get('param')

        if param in ["text", "media"]:
            message_options = MessageOptions(**data.get('post').message_options)

            if param == "text":
                message_options.text = message_options.caption = None
            if param == "media":
                message_options.photo = message_options.video = message_options.animation = None

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
                await db.delete_post(data.get('post').id)
                return await show_create_post(call.message, state)

            kwargs = {"message_options": message_options.model_dump()}
        else:
            kwargs = {param: None}

        post = await db.update_post(
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

    if data.get('param') == "cpm_price":
        post: Post = data.get("post")
        chosen = data.get("chosen", post.chat_ids)
        display_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen[:10]
        )
        return await call.message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    await answer_post(call.message, state)


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

    post: Post = data.get("post")
    if param in ["text", "media"]:
        message_options = MessageOptions(**post.message_options)

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

        kwargs = {"message_options": message_options.model_dump()}

    else:
        value = message.text

        if param in ["cpm_price"]:
            try:
                value = int(value)

            except ValueError:
                return await message.answer(
                    text("error_value")
                )
        else:
            if param == "buttons":
                post.buttons = value
            else:
                c = 0
                dict_react = {'rows': []}
                for a, row in enumerate(message.text.split('\n')):
                    reactions = []
                    for react in row.split('|'):
                        reactions.append({'id': c, 'react': react, 'users': []})
                        c += 1
                    dict_react['rows'].append({'id': a, 'reactions': reactions})

                post.reaction = dict_react
                value = dict_react

            try:
                post: Post = data.get("post")
                check = await message.answer("...", reply_markup=keyboards.manage_post(post))
                await check.delete()
            except (IndexError, TypeError):
                return await message.answer(
                    text("error_value")
                )

        kwargs = {param: value}

    if data.get("is_published"):
        await db.update_published_posts_by_post_id(
            post_id=post.post_id,
            **kwargs
        )
        post = await db.get_published_post_by_id(post.id)
    else:
        post = await db.update_post(
            post_id=post.id,
            return_obj=True,
            **kwargs
        )

    # Update backup message if content changed
    if param in ["text", "media", "buttons", "reaction"]:
        await edit_backup_message(post)
        
        # Refresh post object to get updated backup_message_id if fallback occurred
        if data.get("is_published"):
            post = await db.get_published_post_by_id(post.id)
        else:
            post = await db.get_post(post.id)

        # Update live messages if published
        if data.get("is_published"):
            message_options = MessageOptions(**post.message_options)
            reply_markup = keyboards.post_kb(post=post)
            await update_live_messages(post.post_id, message_options, reply_markup=reply_markup)

    await state.clear()
    data['post'] = post
    await state.update_data(data)

    await message.bot.delete_message(
        message.chat.id,
        data.get("input_msg_id")
    )

    if param == "cpm_price":
        chosen = data.get("chosen", post.chat_ids)
        display_objects = await db.get_user_channels(
            user_id=message.from_user.id,
            from_array=chosen[:10]
        )
        return await message.answer(
            text("choice_channels:post").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    await answer_post(message, state)


async def add_hide_value(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await call.message.delete()

    if temp[1] == "...":
        return await call.answer()

    if temp[1] == "add":
        await state.update_data(
            hide_step="button_name"
        )
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide")
        )
        await state.set_state(AddHide.button_name)


async def back_input_button_name(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    await state.clear()
    await state.update_data(data)
    await call.message.delete()

    hide_step = data.get("hide_step")
    temp = call.data.split("|")

    if len(temp) == 1 or hide_step == "button_name" or temp[1] == "cancel":
        return await call.message.answer(
            text("manage:post:new:hide"),
            reply_markup=keyboards.param_hide(
                post=data.get('post')
            )
        )
    if hide_step == "not_member":
        await call.message.answer(
            text("manage:post:add:param:hide:button_name"),
            reply_markup=keyboards.back(data="BackButtonHide")
        )
        return await state.set_state(AddHide.button_name)

    if hide_step == "for_member":
        await call.message.answer(
            text("manage:post:add:param:hide:not_member"),
            reply_markup=keyboards.param_hide_back()
        )
        return await state.set_state(AddHide.not_member_text)


async def get_button_name(message: types.Message, state: FSMContext):
    await state.update_data(
        hide_button_name=message.text,
        hide_step="not_member"
    )

    await message.answer(
        text("manage:post:add:param:hide:not_member"),
        reply_markup=keyboards.param_hide_back()
    )
    await state.set_state(AddHide.not_member_text)


async def get_not_member_text(message: types.Message, state: FSMContext):
    if len(message.text) > 200:
        return await message.answer(
            text("error_200_length_text")
        )

    await state.update_data(
        hide_not_member_text=message.text,
        hide_step="for_member"
    )

    await message.answer(
        text("manage:post:add:param:hide:for_member"),
        reply_markup=keyboards.param_hide_back()
    )
    await state.set_state(AddHide.for_member_text)


async def get_for_member_text(message: types.Message, state: FSMContext):
    if len(message.text) > 200:
        return await message.answer(
            text("error_200_length_text")
        )

    await state.update_data(
        hide_for_member_text=message.text
    )
    data = await state.get_data()
    post: Post = data.get('post')

    if post.hide is None:
        post.hide = []

    post.hide.append(
        {
            'id': len(post.hide) + 1,
            'button_name': data.get("hide_button_name"),
            'for_member': data.get("hide_for_member_text"),
            'not_member': data.get("hide_not_member_text"),
        }
    )

    post = await db.update_post(
        post_id=post.id,
        return_obj=True,
        hide=post.hide
    )

    await state.clear()
    await state.update_data(
        post=post,
        show_more=data.get("show_more"),
        param="hide"
    )

    await message.answer(
        text("manage:post:new:hide"),
        reply_markup=keyboards.param_hide(
            post=post
        )
    )


async def choice_channels(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    chosen: list = data.get("chosen")
    current_folder_id = data.get("current_folder_id")

    # Determine what to show
    if current_folder_id:
        # Inside a folder
        folder = await db.get_folder_by_id(current_folder_id)
        objects = []
        if folder and folder.content:
            for chat_id in folder.content:
                channel = await db.get_channel_by_chat_id(int(chat_id))
                if channel:
                    objects.append(channel)
        folders = []
    else:
        # Root view
        objects = await db.get_user_channels_without_folders(
            user_id=call.from_user.id
        )
        folders = await db.get_folders(
            user_id=call.from_user.id
        )

    if temp[1] == "next_step":
        if not chosen:
            return await call.answer(
                text('error_min_choice')
            )

        # Fetch all chosen channels for display
        all_chosen_objects = []
        # We need to fetch all channels that are in 'chosen' list to display their titles
        # This might be expensive if list is huge, but usually it's fine.
        # We can use 'db.get_user_channels' with 'from_array' or similar if available, 
        # or just fetch all user channels and filter.
        # 'db.get_user_channels' has 'from_array'.
        all_chosen_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen
        )

        return await call.message.edit_text(
            text("manage:post:finish_params").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in all_chosen_objects[:10]
                )
            ),
            reply_markup=keyboards.finish_params(
                obj=data.get('post')
            )
        )

    if temp[1] == "cancel":
        if current_folder_id:
            # Go back to root
            await state.update_data(current_folder_id=None)
            # Re-fetch root data
            objects = await db.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            folders = await db.get_folders(
                user_id=call.from_user.id
            )
            # Reset temp[2] (remover) to 0 when switching views
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            # Exit
            await call.message.delete()
            return await answer_post(call.message, state)

    if temp[1] in ['next', 'back']:
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders,
                remover=int(temp[2])
            )
        )

    if temp[1] == "choice_all":
        # Select all visible objects (channels)
        # If in folder, objects are channels in folder.
        # If in root, objects are loose channels.
        # Folders are not "selected" in bulk.
        
        current_ids = [i.chat_id for i in objects]
        
        # Check if all current_ids are in chosen
        all_selected = all(cid in chosen for cid in current_ids)
        
        if all_selected:
            # Deselect all visible
            for cid in current_ids:
                if cid in chosen:
                    chosen.remove(cid)
        else:
            # Select all visible
            for cid in current_ids:
                if cid not in chosen:
                    chosen.append(cid)

    if temp[1].replace("-", "").isdigit():
        resource_id = int(temp[1])
        resource_type = temp[3] if len(temp) > 3 else None

        if resource_type == 'folder':
            # Enter folder
            await state.update_data(current_folder_id=resource_id)
            # Re-fetch folder data
            folder = await db.get_folder_by_id(resource_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    channel = await db.get_channel_by_chat_id(int(chat_id))
                    if channel:
                        objects.append(channel)
            folders = []
            # Reset remover
            temp = list(temp)
            if len(temp) > 2:
                temp[2] = '0'
            else:
                temp.append('0')
        else:
            # Toggle channel
            if resource_id in chosen:
                chosen.remove(resource_id)
            else:
                channel = await db.get_channel_by_chat_id(resource_id)
                if not channel.subscribe:
                    return await call.answer(
                        text("error_sub_channel")
                    )
                chosen.append(resource_id)

    await state.update_data(
        chosen=chosen
    )
    
    # Re-calculate display list for message text (show selected channels)
    # We want to show some of the selected channels.
    # We can use the 'objects' list if it contains selected ones, but 'chosen' might contain channels not in 'objects' (e.g. from other folders).
    # So we should probably fetch a few selected channels to display.
    display_objects = await db.get_user_channels(
        user_id=call.from_user.id,
        from_array=chosen[:10]
    )

    await call.message.edit_text(
        text("choice_channels:post").format(
            len(chosen),
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in display_objects
            )
        ),
        reply_markup=keyboards.choice_objects(
            resources=objects,
            chosen=chosen,
            folders=folders,
            remover=int(temp[2]) if temp[1] in ['choice_all', 'next', 'back'] or temp[1].replace("-", "").isdigit() else 0
        )
    )


async def finish_params(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    if temp[1] == 'cancel':
        current_folder_id = data.get("current_folder_id")
        
        if current_folder_id:
            folder = await db.get_folder_by_id(current_folder_id)
            objects = []
            if folder and folder.content:
                for chat_id in folder.content:
                    channel = await db.get_channel_by_chat_id(int(chat_id))
                    if channel:
                        objects.append(channel)
            folders = []
        else:
            objects = await db.get_user_channels_without_folders(
                user_id=call.from_user.id
            )
            folders = await db.get_folders(
                user_id=call.from_user.id
            )

        # Re-calculate display list for message text
        display_objects = await db.get_user_channels(
            user_id=call.from_user.id,
            from_array=chosen[:10]
        )

        return await call.message.edit_text(
            text("choice_channels:post").format(
                len(chosen),
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in display_objects
                )
            ),
            reply_markup=keyboards.choice_objects(
                resources=objects,
                chosen=chosen,
                folders=folders
            )
        )

    if temp[1] == "report":
        post = await db.update_post(
            post_id=post.id,
            return_obj=True,
            report=not post.report
        )
        await state.update_data(
            post=post
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.finish_params(
                obj=post
            )
        )

    if temp[1] == "cpm_price":
        if not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await state.update_data(
            param=temp[1]
        )
        await call.message.delete()
        message_text = text("manage:post:new:{}".format(temp[1]))
        
        input_msg = await call.message.answer(
            message_text,
            reply_markup=keyboards.param_cancel(
                param=temp[1]
            )
        )
        await state.set_state(Posting.input_value)
        await state.update_data(
            input_msg_id=input_msg.message_id
        )
        return

    if temp[1] == "delete_time":
        await call.message.edit_text(
            text("manage:post:new:delete_time"),
            reply_markup=keyboards.choice_delete_time()
        )

    if temp[1] == "send_time":
        if post.cpm_price and not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await call.message.edit_text(
            text("manage:post:new:send_time"),
            reply_markup=keyboards.back(data="BackSendTimePost")
        )
        await state.set_state(Posting.input_send_time)

    if temp[1] == "public":
        if post.cpm_price and not post.delete_time:
            return await call.answer(text("error_cpm_without_timer"), show_alert=True)

        await call.message.edit_text(
            text("manage:post:accept:public").format(
                "\n".join(
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                ),
                f"{int(post.delete_time / 3600)} ч."  # type: ignore
                if post.delete_time else text("manage:post:del_time:not")
            ),
            reply_markup=keyboards.accept_public()
        )


async def choice_delete_time(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")

    delete_time = post.delete_time
    if temp[1].isdigit():
        delete_time = int(temp[1])
    if temp[1] == "off":
        delete_time = None

    if post.delete_time != delete_time:
        if data.get("is_published"):
            await db.update_published_posts_by_post_id(
                post_id=post.post_id,
                delete_time=delete_time
            )
            # Refresh post object
            post = await db.get_published_post_by_id(post.id)
        else:
            post = await db.update_post(
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
                post=post,
                is_published=data.get("is_published")
            )
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
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
            obj=data.get('post')
        )
    )


async def cancel_send_time(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
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
            reply_markup=keyboards.manage_remain_post(
                post=data.get("post"),
                is_published=data.get("is_published")
            )
        )

    chosen: list = data.get("chosen")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

    await call.message.edit_text(
        text("manage:post:finish_params").format(
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
            obj=data.get('post')
        )
    )


async def get_send_time(message: types.Message, state: FSMContext):
    input_date = message.text.strip()
    parts = input_date.split()

    try:
        # Формат: DD.MM.YYYY HH:MM
        if len(parts) == 2 and len(parts[0].split('.')) == 3 and ':' in parts[1]:
            date = datetime.strptime(input_date, "%d.%m.%Y %H:%M")
        
        # Формат: HH:MM DD.MM.YYYY
        elif len(parts) == 2 and ':' in parts[0] and len(parts[1].split('.')) == 3:
            date = datetime.strptime(f"{parts[1]} {parts[0]}", "%d.%m.%Y %H:%M")
        
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
    post: Post = data.get('post')

    if is_edit:
        post = await db.update_post(
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
            text("post:content").format(
                *send_date_values,
                data.get("channel").emoji_id,
                data.get("channel").title
            ),
            reply_markup=keyboards.manage_remain_post(
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
        sort_by="posting"
    )

    await message.answer(
        text("manage:post:accept:date").format(
            *date_values,
            "\n".join(
                text("resource_title").format(
                    obj.emoji_id,
                    obj.title
                ) for obj in objects
                if obj.chat_id in chosen[:10]
            ),
            f"{int(post.delete_time / 3600)} ч."  # type: ignore
            if post.delete_time else text("manage:post:del_time:not")
        ),
        reply_markup=keyboards.accept_date()
    )


async def accept(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    post: Post = data.get("post")
    chosen: list = data.get("chosen", post.chat_ids)
    send_time: int = data.get("send_time")
    is_edit: bool = data.get("is_edit")
    objects = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )

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
                    text("resource_title").format(
                        obj.emoji_id,
                        obj.title
                    ) for obj in objects
                    if obj.chat_id in chosen[:10]
                )
            )
            reply_markup = keyboards.finish_params(
                obj=post
            )
        if is_edit:
            message_text = text("post:content").format(
                *data.get("send_date_values"),
                data.get("channel").emoji_id,
                data.get("channel").title
            )
            reply_markup = keyboards.manage_remain_post(
                post=data.get("post"),
                is_published=data.get("is_published")
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

    logger.info(f"Accepting post {post.id}. Chosen channels: {chosen}")

    await db.update_post(
        post_id=post.id,
        **kwargs
    )

    # Send to backup if not already sent
    if not post.backup_message_id:
        backup_chat_id, backup_message_id = await send_to_backup(post)
        if backup_chat_id and backup_message_id:
            await db.update_post(
                post_id=post.id,
                backup_chat_id=backup_chat_id,
                backup_message_id=backup_message_id
            )

    if send_time:
        message_text = text("manage:post:success:date").format(
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
        message_text = text("manage:post:success:public").format(
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
        reply_markup=keyboards.create_finish()
    )


async def click_hide(call: types.CallbackQuery):
    temp = call.data.split('|')

    published_post = await db.get_published_post(
        chat_id=call.message.sender_chat.id,
        message_id=call.message.message_id,
    )
    if not published_post:
        return

    user = await call.bot.get_chat_member(
        chat_id=call.message.sender_chat.id,
        user_id=call.from_user.id
    )

    hide_model = Hide(hide=published_post.hide)
    for row_hide in hide_model.hide:
        if row_hide.id != int(temp[1]):
            continue

        await call.answer(
            row_hide.for_member if user.status != "left" else row_hide.not_member,
            show_alert=True
        )


async def click_react(call: types.CallbackQuery):
    temp = call.data.split('|')

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
        post_id=published_post.id,
        return_obj=True,
        reaction=react_model.model_dump()
    )
    await call.message.edit_reply_markup(
        reply_markup=keyboards.post_kb(
            post=post
        )
    )


def hand_add():
    router = Router()
    # Manage
    router.message.register(get_message, Posting.input_message, F.text | F.photo | F.video | F.animation)
    router.callback_query.register(cancel_message, F.data.split("|")[0] == "InputPostCancel")
    router.callback_query.register(manage_post, F.data.split("|")[0] == "ManagePost")
    # Values
    router.callback_query.register(cancel_value, F.data.split("|")[0] == "ParamCancel")
    router.message.register(get_value, Posting.input_value, F.text | F.photo | F.video | F.animation)
    # Hide
    router.callback_query.register(add_hide_value, F.data.split("|")[0] == "ParamHide")
    router.callback_query.register(back_input_button_name, F.data.split("|")[0] == "BackButtonHide")
    router.message.register(get_button_name, AddHide.button_name, F.text)
    router.message.register(get_not_member_text, AddHide.not_member_text, F.text)
    router.message.register(get_for_member_text, AddHide.for_member_text, F.text)
    # Choice
    router.callback_query.register(choice_channels, F.data.split("|")[0] == "ChoicePostChannels")
    # Finish Params
    router.callback_query.register(finish_params, F.data.split("|")[0] == "FinishPostParams")
    router.callback_query.register(choice_delete_time, F.data.split("|")[0] == "GetDeleteTimePost")
    router.callback_query.register(cancel_send_time, F.data.split("|")[0] == "BackSendTimePost")
    router.message.register(get_send_time, Posting.input_send_time, F.text)
    # Accept
    router.callback_query.register(accept, F.data.split("|")[0] == "AcceptPost")
    # Clicks
    router.callback_query.register(click_hide, F.data.split("|")[0] == "ClickHide")
    router.callback_query.register(click_react, F.data.split("|")[0] == "ClickReact")

    return router
