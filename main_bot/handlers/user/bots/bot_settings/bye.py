"""
Модуль настройки прощальных сообщений.

Реализует:
- Управление активностью прощаний
- Настройку текста/медиа прощального сообщения
- Предпросмотр сообщения
- Обработку ввода контента сообщения
"""

import logging


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
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Bots Bye Choice")
async def choice(
    call: types.CallbackQuery,
    state: FSMContext,
    db_obj: Database,
    channel_settings: ChannelBotSetting,
) -> None:
    """
    Меню настройки прощального сообщения.
    Обрабатывает включение/выключение, добавление сообщения, просмотр.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
        db_obj (Database): БД бота.
        channel_settings (ChannelBotSetting): Настройки канала.
    """
    temp = call.data.split("|")
    hello_data = ByeAnswer(**channel_settings.bye)
    data = await state.get_data()

    if temp[1] == "cancel":
        await call.message.delete()
        await show_channel_setting(call.message, db_obj, state)
        return

    if temp[1] in ["active", "message"]:
        if temp[1] == "active":
            hello_data.active = not hello_data.active
        if temp[1] == "message":
            if not hello_data.message:
                await call.message.edit_text(
                    text("input_bye_message"),
                    reply_markup=keyboards.back(data="AddByeBack"),
                )
                await state.set_state(Bye.message)
                return

            if hello_data.message:
                hello_data.message = None
                hello_data.active = False

        if hello_data.active and not hello_data.message:
            await call.answer(text("error:bye:add_message"))
            return

        await db.channel_bot_settings.update_channel_bot_setting(
            chat_id=data.get("chat_id"), bye=hello_data.model_dump()
        )
        setting = await db.channel_bot_settings.get_channel_bot_setting(
            chat_id=data.get("chat_id")
        )

        await call.message.delete()
        await show_bye(call.message, setting)
        return

    if temp[1] == "check":
        if not hello_data.message:
            await call.answer(text("error:bye:add_message"))
            return

        await call.message.delete()
        await answer_message(call.message, hello_data.message)
        await show_bye(call.message, channel_settings)


@safe_handler("Bots Bye Back")
async def back(
    call: types.CallbackQuery, state: FSMContext, channel_settings: ChannelBotSetting
) -> None:
    """
    Возврат в меню настройки прощаний из подменю (ввод текста).

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
        channel_settings (ChannelBotSetting): Настройки канала.
    """
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()
    await show_bye(call.message, channel_settings)


@safe_handler("Bots Bye Get Message")
async def get_message(
    message: types.Message, state: FSMContext, channel_settings: ChannelBotSetting
) -> None:
    """
    Обработка ввода прощального сообщения пользователем.
    Сохраняет текст/медиа и обновляет настройки.

    Аргументы:
        message (types.Message): Сообщение с контентом.
        state (FSMContext): Контекст состояния.
        channel_settings (ChannelBotSetting): Настройки канала.
    """
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        await message.answer(text("error_length_text"))
        return

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptions(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    hello_data = ByeAnswer(**channel_settings.bye)
    hello_data.message = message_options

    data = await state.get_data()
    await db.channel_bot_settings.update_channel_bot_setting(
        chat_id=data.get("chat_id"), bye=hello_data.model_dump()
    )
    setting = await db.channel_bot_settings.get_channel_bot_setting(
        chat_id=data.get("chat_id")
    )

    await state.clear()
    await state.update_data(**data)

    await message.answer(text("success_add_bye"))
    await show_bye(message, setting)


def get_router() -> Router:
    """
    Регистрация роутеров модуля прощаний.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageBye")
    router.callback_query.register(back, F.data.split("|")[0] == "AddByeBack")
    router.message.register(
        get_message, Bye.message, F.text | F.photo | F.video | F.animation
    )

    return router
