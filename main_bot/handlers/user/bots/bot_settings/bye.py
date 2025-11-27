from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database
from hello_bot.handlers.user.menu import show_bye
from hello_bot.states.user import Bye
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import Media, MessageOptions, ByeAnswer
from hello_bot.utils.functions import answer_message
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from main_bot.database.db import db
from main_bot.handlers.user.bots.bot_settings.menu import show_channel_setting


async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database, channel_settings: ChannelBotSetting):
    temp = call.data.split('|')
    hello = ByeAnswer(**channel_settings.bye)
    data = await state.get_data()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_channel_setting(call.message, db_obj, state)

    if temp[1] in ["active", "message"]:
        if temp[1] == "active":
            hello.active = not hello.active
        if temp[1] == "message":
            if not hello.message:
                await call.message.edit_text(
                    text("input_bye_message"),
                    reply_markup=keyboards.back(
                        data="AddByeBack"
                    )
                )
                return await state.set_state(Bye.message)

            if hello.message:
                hello.message = None
                hello.active = False

        if hello.active and not hello.message:
            return await call.answer(
                text("error:bye:add_message")
            )

        await db.update_channel_bot_setting(
            chat_id=data.get("chat_id"),
            bye=hello.model_dump()
        )
        setting = await db.get_channel_bot_setting(
            chat_id=data.get("chat_id")
        )

        await call.message.delete()
        return await show_bye(call.message, setting)

    if temp[1] == "check":
        if not hello.message:
            return await call.answer(
                text("error:bye:add_message")
            )

        await call.message.delete()
        await answer_message(call.message, hello.message)
        await show_bye(call.message, channel_settings)


async def back(call: types.CallbackQuery, state: FSMContext, channel_settings: ChannelBotSetting):
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    return await show_bye(call.message, channel_settings)


async def get_message(message: types.Message, state: FSMContext, channel_settings: ChannelBotSetting):
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

    hello = ByeAnswer(**channel_settings.bye)
    hello.message = message_options

    data = await state.get_data()
    await db.update_channel_bot_setting(
        chat_id=data.get("chat_id"),
        bye=hello.model_dump()
    )
    setting = await db.get_channel_bot_setting(
        chat_id=data.get("chat_id")
    )

    await state.clear()
    await state.update_data(**data)

    await message.answer(text("success_add_bye"))
    await show_bye(message, setting)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageBye")
    router.callback_query.register(back, F.data.split("|")[0] == "AddByeBack")
    router.message.register(get_message, Bye.message, F.text | F.photo | F.video | F.animation)

    return router
