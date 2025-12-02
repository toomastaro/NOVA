import logging
from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.channel.model import Channel
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.handlers.user.posting.menu import show_content
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.functions import answer_post
from main_bot.utils.lang.language import text


logger = logging.getLogger(__name__)


async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ["next", "back"]:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=channels,
                remover=int(temp[2])
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_posting(call.message)

    chat_id = int(temp[1])
    logger.info(f"User {call.from_user.id} selected channel {chat_id} for content view")
    channel = await db.get_channel_by_chat_id(chat_id)

    day = datetime.today()
    posts = await db.get_posts(channel.chat_id, day)
    day_values = (day.day, text("month").get(str(day.month)), day.year,)

    await state.update_data(
        channel=channel,
        day=day,
        day_values=day_values,
        show_more=False
    )

    await call.message.delete()
    await call.message.answer(
        text("channel:content").format(
            *day_values,
            channel.emoji_id,
            channel.title,
            text("no_content") if not posts else text("has_content").format(len(posts))
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts,
            day=day
        )
    )


async def choice_row_content(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(f"No state data found for user {call.from_user.id} in choice_row_content")
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_content(call.message)

    channel: Channel = data.get("channel")
    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] in ['next_day', 'next_month', 'back_day', 'back_month', "choice_day", "show_more"]:
        if temp[1] == "choice_day":
            day = datetime.strptime(temp[2], '%Y-%m-%d')
        elif temp[1] == "show_more":
            show_more = not show_more
        else:
            day = day - timedelta(days=int(temp[2]))

        posts = await db.get_posts(channel.chat_id, day)
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
            show_more=show_more
        )

        return await call.message.edit_text(
            text("channel:content").format(
                *day_values,
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more
            )
        )

    if temp[1] == "show_all":
        posts = await db.get_posts(channel.chat_id, only_scheduled=True)
        return await call.message.edit_text(
            text("channel:show_all:content").format(
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_time_objects(
                objects=posts
            )
        )

    if temp[1] == "...":
        return await call.answer()
    
    # Handle PublishedPost
    if call.data.startswith("ContentPublishedPost"):
        post_id = int(temp[1])
        logger.info(f"User {call.from_user.id} viewing published post {post_id}")
        post = await db.get_published_post_by_id(post_id)
        # Use created_timestamp as send_time for display
        send_date = datetime.fromtimestamp(post.created_timestamp)
        send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)
        
        # Convert PublishedPost to Post-like object for editing compatibility if needed
        # or just pass it as 'post' if create_post.py handles it.
        # create_post.py expects 'post' to have 'id', 'message_options', etc.
        # PublishedPost now has message_options.
        
        await state.update_data(
            post=post,
            send_date_values=send_date_values,
            is_edit=True, # Enable editing
            is_published=True # Flag to indicate it's a published post
        )

        post_message = await answer_post(call.message, state, from_edit=True)
        await state.update_data(
            post_message=post_message,
        )

        await call.message.delete()
        await call.message.answer(
            text("post:content").format(
                *send_date_values,
                channel.emoji_id,
                channel.title
            ),
            reply_markup=keyboards.manage_remain_post(
                post=post,
                is_published=True
            )
        )
        return

    post_id = int(temp[1])
    post = await db.get_post(post_id)
    send_date = datetime.fromtimestamp(post.send_time)
    send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)
    await state.update_data(
        post=post,
        send_date_values=send_date_values,
        is_edit=True
    )

    post_message = await answer_post(call.message, state, from_edit=True)
    await state.update_data(
        post_message=post_message,
    )

    await call.message.delete()
    await call.message.answer(
        text("post:content").format(
            *send_date_values,
            channel.emoji_id,
            channel.title
        ),
        reply_markup=keyboards.manage_remain_post(
            post=post
        )
    )


async def choice_time_objects(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    channel: Channel = data.get("channel")

    if temp[1] in ["next", "back"]:
        posts = await db.get_posts(channel.chat_id)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(
                objects=posts
            )
        )

    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] == "cancel":
        posts = await db.get_posts(channel.chat_id, day)
        return await call.message.edit_text(
            text("channel:content").format(
                *data.get("day_values"),
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more
            )
        )


async def manage_remain_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        day = data.get('day')
        posts = await db.get_posts(data.get("channel").chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        return await call.message.edit_text(
            text("channel:content").format(
                *data.get("day_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day
            )
        )

    if temp[1] == "delete":
        callback_data = "AcceptDeletePublishedPost" if data.get("is_published") else "AcceptDeletePost"
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(data=callback_data)
        )

    if temp[1] == "change":
        await call.message.delete()
        post_message = data.get("post_message")
        reply_markup = keyboards.manage_post(
            post=data.get('post'),
            is_edit=data.get('is_edit')
        )
        
        if isinstance(post_message, types.Message):
            await post_message.edit_reply_markup(reply_markup=reply_markup)
        else:
            # It's a MessageId object (from copyMessage)
            await call.bot.edit_message_reply_markup(
                chat_id=call.message.chat.id,
                message_id=post_message.message_id,
                reply_markup=reply_markup
            )


async def accept_delete_row_content(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    day = data.get("day")
    day_values = data.get("day_values")
    send_date_values = data.get("send_date_values")
    channel = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("post:content").format(
                *send_date_values,
                channel.emoji_id,
                channel.title
            ),
            reply_markup=keyboards.manage_remain_post(
                post=post,
                is_published=data.get("is_published")
            )
        )

    if temp[1] == "accept":
        await db.delete_post(post.id)
        posts = await db.get_posts(channel.chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)

        return await call.message.edit_text(
            text("channel:content").format(
                *day_values,
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day
            )
        )



async def manage_published_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        day = data.get('day')
        posts = await db.get_posts(data.get("channel").chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        return await call.message.edit_text(
            text("channel:content").format(
                *data.get("day_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day
            )
        )

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeletePublishedPost"
            )
        )


async def accept_delete_published_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        logger.warning(f"No state data found for user {call.from_user.id} in accept_delete_published_post")
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    day = data.get("day")
    day_values = data.get("day_values")
    send_date_values = data.get("send_date_values")
    channel = data.get("channel")
    post = data.get("post")

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("post:content").format(
                *send_date_values,
                channel.emoji_id,
                channel.title
            ),
            reply_markup=keyboards.manage_published_post(
                post=post
            )
        )

    if temp[1] == "accept":
        logger.info(f"User {call.from_user.id} deleting published post {post.id} (message_id: {post.message_id}) and all related posts")
        
        # Fetch all related published posts
        related_posts = await db.get_published_posts_by_post_id(post.post_id)
        
        # Delete from Telegram for all channels
        ids_to_delete = []
        for p in related_posts:
            ids_to_delete.append(p.id)
            try:
                await call.bot.delete_message(p.chat_id, p.message_id)
            except Exception as e:
                logger.error(f"Error deleting message {p.message_id} from {p.chat_id}: {e}", exc_info=True)

        # Soft Delete all from DB
        if ids_to_delete:
            await db.soft_delete_published_posts(ids_to_delete)
        
        posts = await db.get_posts(channel.chat_id, day)

        post_message = data.get("post_message")
        if isinstance(post_message, types.Message):
            await post_message.delete()
        else:
            await call.bot.delete_message(call.message.chat.id, post_message.message_id)
        return await call.message.edit_text(
            text("channel:content").format(
                *day_values,
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day
            )
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice_channel, F.data.split("|")[0] == "ChoiceObjectContentPost")
    router.callback_query.register(choice_row_content, F.data.split("|")[0].in_({"ContentPost", "ContentPublishedPost"}))
    router.callback_query.register(choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentPost")
    router.callback_query.register(manage_remain_post, F.data.split("|")[0] == "ManageRemainPost")
    router.callback_query.register(manage_published_post, F.data.split("|")[0] == "ManagePublishedPost")
    router.callback_query.register(accept_delete_row_content, F.data.split("|")[0] == "AcceptDeletePost")
    router.callback_query.register(accept_delete_published_post, F.data.split("|")[0] == "AcceptDeletePublishedPost")
    return router
