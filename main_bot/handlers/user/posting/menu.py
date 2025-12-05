from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import Posting
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    temp = call.data.split('|')

    menu = {
        'create_post': {
            'cor': show_create_post,
            'args': (call.message, state,)
        },
        'channels': {
            'cor': show_settings,
            'args': (call.message,)
        },
        'content_plan': {
            'cor': show_content,
            'args': (call.message,)
        },
    }

    cor, args = menu[temp[1]].values()

    await call.message.delete()
    await cor(*args)


async def show_create_post(message: types.Message, state: FSMContext):
    await message.answer(
        text('input_message'),
        reply_markup=keyboards.cancel(
            data="InputPostCancel"
        )
    )
    await state.set_state(Posting.input_message)


async def show_settings(message: types.Message):
    channels = await db.get_user_channels(
        user_id=message.chat.id,
        sort_by="posting"
    )
    await message.answer(
        text('channels_text'),
        reply_markup=keyboards.channels(
            channels=channels
        )
    )


async def show_content(message: types.Message):
    channels = await db.get_user_channels(
        user_id=message.chat.id
    )
    await message.answer(
        text('choice_channel:content'),
        reply_markup=keyboards.choice_object_content(
            channels=channels
        )
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "MenuPosting")
    return router
