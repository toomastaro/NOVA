import time
from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards.keyboards import keyboards
from main_bot.states.user import Posting
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    temp = call.data.split("|")

    menu = {
        "create_post": {
            "cor": show_create_post,
            "args": (
                call.message,
                state,
            ),
        },
        "channels": {"cor": show_settings, "args": (call.message,)},
        "content_plan": {"cor": show_content, "args": (call.message,)},
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_create_post(message: types.Message, state: FSMContext):
    channels = await db.get_user_channels(user_id=message.chat.id, sort_by="subscribe")
    
    if not channels:
        await message.answer(text("not_found_channels"))
        return

    await message.answer(
        text("choice_channels:post").format(len(channels), ""),
        reply_markup=keyboards.choice_channels_for_post(channels=channels)
    )
    await state.set_state(Posting.choice_channel)


async def process_choice_channel(call: types.CallbackQuery, state: FSMContext):
    data = call.data.split("|")
    action = data[1]

    if action == "cancel":
        await state.clear()
        await call.message.delete()
        await call.message.answer(
            text("reply_menu:posting"), reply_markup=keyboards.posting_menu()
        )
        return

    if action in ["next", "back"]:
        remover = int(data[2])
        channels = await db.get_user_channels(user_id=call.message.chat.id, sort_by="subscribe")
        await call.message.edit_reply_markup(
            reply_markup=keyboards.choice_channels_for_post(
                channels=channels, remover=remover
            )
        )
        return

    channel_id = int(action)
    channel = await db.get_channel_by_chat_id(chat_id=channel_id)

    if not channel.subscribe or channel.subscribe < time.time():
        await call.answer(text("error_sub_channel"), show_alert=True)
        return

    await state.update_data(channel_id=channel_id)
    await call.message.delete()
    await call.message.answer(
        text("input_message"), reply_markup=keyboards.cancel(data="InputPostCancel")
    )
    await state.set_state(Posting.input_message)


async def show_settings(message: types.Message):
    channels = await db.get_user_channels(user_id=message.chat.id, sort_by="posting")
    await message.answer(
        text("channels_text"), reply_markup=keyboards.channels(channels=channels)
    )


async def show_content(message: types.Message):
    channels = await db.get_user_channels(user_id=message.chat.id)
    await message.answer(
        text("choice_channel:content"),
        reply_markup=keyboards.choice_object_content(channels=channels),
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuPosting")
    router.callback_query.register(process_choice_channel, Posting.choice_channel, F.data.startswith("ChoiceChannelPost"))
    return router
