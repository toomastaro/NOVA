from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.channel.model import Channel
from main_bot.database.db import db
from main_bot.database.types import Status
from main_bot.handlers.user.menu import start_bots
from main_bot.handlers.user.bots.menu import show_content
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.functions import answer_bot_post
from main_bot.utils.lang.language import text


async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ["next", "back"]:
        channels = await db.get_bot_channels(call.from_user.id)
        objects = await db.get_user_channels(call.from_user.id, from_array=[i.id for i in channels])

        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=objects,
                remover=int(temp[2]),
                data="ChoiceObjectContentBots"
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_bots(call.message)

    bot_id = int(temp[1])
    channel = await db.get_channel_by_chat_id(bot_id)

    day = datetime.today()
    posts = await db.get_bot_posts(channel.chat_id, day)
    day_values = (day.day, text("month").get(str(day.month)), day.year,)

    await state.update_data(
        channel=channel,
        day=day,
        day_values=day_values,
        show_more=False
    )

    await call.message.delete()
    await call.message.answer(
        text("bot:content").format(
            *day_values,
            channel.emoji_id,
            channel.title,
            text("no_content") if not posts else text("has_content").format(len(posts))
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts,
            day=day,
            data="ContentBotPost"
        )
    )


async def choice_row_content(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
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

        posts = await db.get_bot_posts(channel.chat_id, day)
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
            show_more=show_more
        )

        return await call.message.edit_text(
            text("bot:content").format(
                *day_values,
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentBotPost"
            )
        )

    if temp[1] == "show_all":
        posts = await db.get_bot_posts(channel.chat_id)
        return await call.message.edit_text(
            text("bot:show_all:content").format(
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_time_objects(
                objects=posts,
                data="ChoiceTimeObjectContentBots"
            )
        )

    if temp[1] == "...":
        return await call.answer()

    post_id = int(temp[1])
    post = await db.get_bot_post(post_id)

    send_date = datetime.fromtimestamp(post.send_time or post.start_timestamp)
    send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)
    await state.update_data(
        post=post,
        send_date_values=send_date_values,
        is_edit=True
    )

    post_message = await answer_bot_post(call.message, state, from_edit=True)
    await state.update_data(
        post_message=post_message,
    )

    if post.status in [Status.FINISH, Status.ERROR]:
        await call.message.delete()
        return await call.message.answer(
            text("report_finished").format(
                post.success_send,
                post.error_send,
                "Нет" if not post.delete_time else f"{int(post.delete_time / 3600)} ч.",
                datetime.fromtimestamp(post.start_timestamp).strftime(
                    "%d.%m.%Y %H:%M"
                ),
                datetime.fromtimestamp(post.end_timestamp).strftime(
                    "%d.%m.%Y %H:%M"
                ),
                (await call.bot.get_chat(post.admin_id)).username
            ),
            reply_markup=keyboards.back(
                data="ManageRemainBotPost|cancel"
            )
        )

    await call.message.delete()
    await call.message.answer(
        text("bot_post:content").format(
            *send_date_values,
            channel.emoji_id,
            channel.title
        ),
        reply_markup=keyboards.manage_remain_bot_post(
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
        posts = await db.get_bot_posts(channel.chat_id)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(
                objects=posts,
                remover=int(temp[2]),
                data="ChoiceTimeObjectContentBots"
            )
        )

    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] == "cancel":
        posts = await db.get_bot_posts(channel.chat_id, day)
        return await call.message.edit_text(
            text("bot:content").format(
                *data.get("day_values"),
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentBotPost"
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
        posts = await db.get_bot_posts(data.get("channel").chat_id, day)

        await data.get("post_message").delete()
        return await call.message.edit_text(
            text("bot:content").format(
                *data.get("day_values"),
                data.get("channel").emoji_id,
                data.get("channel").title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentBotPost"
            )
        )

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:post"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeleteBotPost"
            )
        )

    if temp[1] == "change":
        await call.message.delete()
        await data.get("post_message").edit_reply_markup(
            reply_markup=keyboards.manage_bot_post(
                post=data.get('post'),
                is_edit=data.get('is_edit')
            )
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
            text("bot_post:content").format(
                *send_date_values,
                channel.emoji_id,
                channel.title
            ),
            reply_markup=keyboards.manage_remain_bot_post(
                post=post
            )
        )

    if temp[1] == "accept":
        await db.delete_bot_post(post.id)
        posts = await db.get_bot_posts(channel.chat_id, day)

        await data.get("post_message").delete()
        return await call.message.edit_text(
            text("bot:content").format(
                *day_values,
                channel.emoji_id,
                channel.title,
                text("no_content") if not posts else text("has_content").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentBotPost"
            )
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice_channel, F.data.split("|")[0] == "ChoiceObjectContentBots")
    router.callback_query.register(choice_row_content, F.data.split("|")[0] == "ContentBotPost")
    router.callback_query.register(choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentBots")
    router.callback_query.register(manage_remain_post, F.data.split("|")[0] == "ManageRemainBotPost")
    router.callback_query.register(accept_delete_row_content, F.data.split("|")[0] == "AcceptDeleteBotPost")
    return router
