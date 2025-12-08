from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.handlers.user.menu import start_posting
from main_bot.keyboards import keyboards
from main_bot.states.user import AddChannel
from main_bot.utils.functions import get_editors
from main_bot.utils.lang.language import text
from main_bot.utils.logger import logging
from main_bot.utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Posting Channel Choice")
async def choice(call: types.CallbackQuery, state: FSMContext):
    temp = call.data.split('|')

    if temp[1] in ['next', 'back']:
        channels = await db.get_user_channels(
            user_id=call.from_user.id,
            sort_by="posting"
        )
        return await call.message.edit_reply_markup(
            reply_markup=keyboards.channels(
                channels=channels,
                remover=int(temp[2])
            )
        )

    if temp[1] == 'cancel':
        await call.message.delete()
        return await start_posting(call.message)

    if temp[1] == 'add':
        await state.set_state(AddChannel.waiting_for_channel)
        
        # Удаляем старое сообщение
        await call.message.delete()
        
        # Отправляем текстовую инструкцию
        return await call.message.answer(
            text=text("channels:add:text"),
            reply_markup=keyboards.add_channel(
                bot_username=(await call.bot.get_me()).username,
            )
        )

    channel = await db.get_channel_by_chat_id(int(temp[1]))
    editors_str = await get_editors(call, channel.chat_id)

    await call.message.edit_text(
        text('channel_info').format(
            channel.title,
            editors_str
        ),
        reply_markup=keyboards.manage_channel()
    )


@safe_handler("Posting Channel Cancel")
async def cancel(call: types.CallbackQuery):
    channels = await db.get_user_channels(
        user_id=call.from_user.id,
        sort_by="posting"
    )
    return await call.message.edit_text(
        text=text("channels_text"),
        reply_markup=keyboards.channels(
            channels=channels,
        )
    )


@safe_handler("Posting Manage Channel")
async def manage_channel(call: types.CallbackQuery):
    temp = call.data.split('|')

    if temp[1] == 'delete':
        return await call.answer(
            text('delete_channel'),
            show_alert=True
        )

    await cancel(call)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoicePostChannel")
    router.callback_query.register(cancel, F.data.split("|")[0] == "BackAddChannelPost")
    router.callback_query.register(manage_channel, F.data.split("|")[0] == "ManageChannelPost")
    return router
