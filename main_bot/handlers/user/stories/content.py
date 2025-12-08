from datetime import datetime, timedelta

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.channel.model import Channel
from main_bot.database.db import db
from main_bot.handlers.user.menu import start_stories
from main_bot.handlers.user.stories.menu import show_content
from main_bot.keyboards import keyboards
from main_bot.utils.functions import answer_story
from main_bot.utils.lang.language import text
from main_bot.utils.error_handler import safe_handler


async def get_days_with_stories(channel_chat_id: int, year: int, month: int) -> set:
    """
    Получает множество дней месяца, в которые есть истории.
    
    Args:
        channel_chat_id: ID канала
        year: Год
        month: Месяц
        
    Returns:
        set: Множество дней (int) с историями
    """
    from calendar import monthrange
    _, last_day = monthrange(year, month)
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, last_day, 23, 59, 59)
    
    # Получаем все истории
    all_month_stories = await db.get_stories(channel_chat_id)
    
    days_with_stories = set()
    for story in all_month_stories:
        story_date = datetime.fromtimestamp(story.send_time)
        if month_start <= story_date <= month_end:
            days_with_stories.add(story_date.day)
    
    return days_with_stories


@safe_handler("Stories Choice Channel")
async def choice_channel(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ["next", "back"]:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="stories"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_object_content(
                channels=channels,
                remover=int(temp[2]),
                data="ChoiceObjectContentStories"
            )
        )

    if temp[1] == "cancel":
        await call.message.delete()
        return await start_stories(call.message)

    chat_id = int(temp[1])
    channel = await db.get_channel_by_chat_id(chat_id)

    day = datetime.today()
    posts = await db.get_stories(channel.chat_id, day)
    day_values = (day.day, text("month").get(str(day.month)), day.year,)

    await state.update_data(
        channel=channel,
        day=day,
        day_values=day_values,
        show_more=False
    )

    days_with_stories = await get_days_with_stories(channel.chat_id, day.year, day.month)

    await call.message.delete()
    await call.message.answer(
        text("channel:content").format(
            channel.title,
            *day_values,
            text("no_content:story") if not posts else text("has_content:story").format(len(posts))
        ),
        reply_markup=keyboards.choice_row_content(
            posts=posts,
            day=day,
            data="ContentStories",days_with_posts=days_with_stories
        )
    )


@safe_handler("Stories Choice Row Content")
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

        posts = await db.get_stories(channel.chat_id, day)
        day_values = (day.day, text("month").get(str(day.month)), day.year,)

        await state.update_data(
            day=day,
            day_values=day_values,
            show_more=show_more
        )

        return await call.message.edit_text(
            text("channel:content").format(
                *day_values,
                channel.title,
                text("no_content:story") if not posts else text("has_content:story").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentStories",days_with_posts=days_with_stories
            )
        )

    if temp[1] == "show_all":
        posts = await db.get_stories(channel.chat_id)
        return await call.message.edit_text(
            text("channel:show_all:content").format(
                channel.title,
                text("no_content:story") if not posts else text("has_content:story").format(len(posts))
            ),
            reply_markup=keyboards.choice_time_objects(
                objects=posts,
                data="ChoiceTimeObjectContentStories"
            )
        )

    if temp[1] == "...":
        return await call.answer()

    post_id = int(temp[1])
    post = await db.get_story(post_id)
    send_date = datetime.fromtimestamp(post.send_time)
    send_date_values = (send_date.day, text("month").get(str(send_date.month)), send_date.year,)
    await state.update_data(
        post=post,
        send_date_values=send_date_values,
        is_edit=True
    )

    post_message = await answer_story(call.message, state, from_edit=True)
    await state.update_data(
        post_message=post_message,
    )

    await call.message.delete()
    await call.message.answer(
        text("story:content").format(
            *send_date_values,
            channel.title
        ),
        reply_markup=keyboards.manage_remain_story(
            post=post
        )
    )


@safe_handler("Stories Choice Time Objects")
async def choice_time_objects(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split("|")
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    channel: Channel = data.get("channel")

    if temp[1] in ["next", "back"]:
        posts = await db.get_stories(channel.chat_id)
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_time_objects(
                objects=posts,
                remover=int(temp[2]),
                data="ChoiceTimeObjectContentStories"
            )
        )

    show_more: bool = data.get("show_more")
    day: datetime = data.get("day")

    if temp[1] == "cancel":
        posts = await db.get_stories(channel.chat_id, day)
        days_with_stories = await get_days_with_stories(channel.chat_id, day.year, day.month)
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *data.get("day_values"),
                text("no_content:story") if not posts else text("has_content:story").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                show_more=show_more,
                data="ContentStories",days_with_posts=days_with_stories
            )
        )


@safe_handler("Stories Manage Remain Post")
async def manage_remain_post(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')
    data = await state.get_data()
    if not data:
        await call.answer(text('keys_data_error'))
        return await call.message.delete()

    if temp[1] == "cancel":
        day = data.get('day')
        posts = await db.get_stories(data.get("channel").chat_id, day)

        days_with_stories = await get_days_with_stories(data.get("channel").chat_id, day.year, day.month)

        await data.get("post_message").delete()
        return await call.message.edit_text(
            text("channel:content").format(
                data.get("channel").title,
                *data.get("day_values"),
                text("no_content:story") if not posts else text("has_content:story").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentStories",days_with_posts=days_with_stories
            )
        )

    if temp[1] == "delete":
        await call.message.edit_text(
            text("accept:delete:story"),
            reply_markup=keyboards.accept_delete_row_content(
                data="AcceptDeleteStories"
            )
        )

    if temp[1] == "change":
        await call.message.delete()
        await data.get("post_message").edit_reply_markup(
            reply_markup=keyboards.manage_story(
                post=data.get('post'),
                is_edit=data.get('is_edit')
            )
        )


@safe_handler("Stories Accept Delete Row Content")
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
            text("story:content").format(
                *send_date_values,
                channel.title
            ),
            reply_markup=keyboards.manage_remain_story(
                post=post
            )
        )

    if temp[1] == "accept":
        await db.delete_post(post.id)
        posts = await db.get_stories(channel.chat_id, day)

        days_with_stories = await get_days_with_stories(channel.chat_id, day.year, day.month)

        await data.get("post_message").delete()
        return await call.message.edit_text(
            text("channel:content").format(
                channel.title,
                *day_values,
                text("no_content:story") if not posts else text("has_content:story").format(len(posts))
            ),
            reply_markup=keyboards.choice_row_content(
                posts=posts,
                day=day,
                data="ContentStories",days_with_posts=days_with_stories
            )
        )


def hand_add():
    router = Router()
    router.callback_query.register(choice_channel, F.data.split("|")[0] == "ChoiceObjectContentStories")
    router.callback_query.register(choice_row_content, F.data.split("|")[0] == "ContentStories")
    router.callback_query.register(choice_time_objects, F.data.split("|")[0] == "ChoiceTimeObjectContentStories")
    router.callback_query.register(manage_remain_post, F.data.split("|")[0] == "ManageRemainStories")
    router.callback_query.register(accept_delete_row_content, F.data.split("|")[0] == "AcceptDeleteStories")
    return router
