from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext

from hello_bot.database.db import Database

from main_bot.database.db import db
from main_bot.handlers.user.bots.bot_settings.menu import (
    show_channel_setting,
    show_hello,
)
from main_bot.states.user import Hello
from main_bot.utils.lang.language import text
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import (
    Media,
    MessageOptionsHello,
)
from main_bot.utils.functions import answer_message
from main_bot.utils.error_handler import safe_handler
import logging

logger = logging.getLogger(__name__)


@safe_handler("Bots Show Manage Hello Message")
async def show_manage_hello_message(message: types.Message, state: FSMContext):
    """Отображение меню управления приветственным сообщением."""
    data = await state.get_data()

    hello_message = await db.channel_bot_hello.get_hello_message(
        message_id=data.get("hello_message_id")
    )
    await message.answer(
        text("manage_hello_message").format(data.get("idx")),
        reply_markup=keyboards.manage_hello_message(hello_message=hello_message),
    )


@safe_handler("Bots Hello Choice")
async def choice(call: types.CallbackQuery, state: FSMContext, db_obj: Database):
    """Выбор приветственного сообщения для настройки."""
    temp = call.data.split("|")
    await call.message.delete()

    if temp[1] == "cancel":
        return await show_channel_setting(call.message, db_obj, state)

    if temp[1] == "add":
        await call.message.answer(
            text("input_hello_message"),
            reply_markup=keyboards.back(data="AddHelloBack"),
        )
        return await state.set_state(Hello.message)

    hello_message_id = int(temp[1])
    await state.update_data(idx=temp[2], hello_message_id=hello_message_id)

    await show_manage_hello_message(call.message, state)


@safe_handler("Bots Manage Hello Message")
async def manage_hello_message(call: types.CallbackQuery, state: FSMContext):
    """Управление настройками приветственного сообщения (вкл/выкл, задержка)."""
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] in ["cancel", "delete"]:
        if temp[1] == "delete":
            await db.channel_bot_hello.delete_hello_message(
                data.get("hello_message_id")
            )

        cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))

        await call.message.delete()
        return await show_hello(call.message, cs)

    hello_message = await db.channel_bot_hello.get_hello_message(
        message_id=data.get("hello_message_id")
    )

    if temp[1] == "on":
        await db.channel_bot_hello.update_hello_message(
            message_id=hello_message.id,
            return_obj=True,
            is_active=not hello_message.is_active,
        )

        await call.message.delete()
        await show_manage_hello_message(call.message, state)

    if temp[1] == "delay":
        await call.message.delete()
        await call.message.answer(
            text("application:delay"),
            reply_markup=keyboards.choice_hello_message_delay(
                current=hello_message.delay
            ),
        )

    if temp[1] == "text_with_name":
        hello_message = await db.channel_bot_hello.get_hello_message(
            message_id=data.get("hello_message_id")
        )
        await db.channel_bot_hello.update_hello_message(
            message_id=hello_message.id,
            return_obj=True,
            text_with_name=not hello_message.text_with_name,
        )

        await call.message.delete()
        await show_manage_hello_message(call.message, state)

    if temp[1] == "change":
        await call.message.delete()

        post_id = await answer_message(
            call.message, MessageOptionsHello(**hello_message.message)
        )
        await state.update_data(post_id=post_id.message_id, is_edit=True)

        await call.message.answer(
            text("edit_hello"), reply_markup=keyboards.manage_hello_message_post()
        )


@safe_handler("Bots Manage Hello Message Post")
async def manage_hello_message_post(call: types.CallbackQuery, state: FSMContext):
    """Редактирование поста приветствия (кнопки, текст)."""
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] == "cancel":
        await state.update_data(is_edit=None)
        await call.bot.delete_message(call.from_user.id, data.get("post_id"))

        await call.message.delete()
        return await show_manage_hello_message(call.message, state)

    await call.message.delete()

    if temp[1] == "url_buttons":
        await call.message.answer(
            text("manage:post:new:buttons"),
            reply_markup=keyboards.back(data="AddHelloBack"),
        )
        return await state.set_state(Hello.buttons)

    if temp[1] == "message":
        await call.message.answer(
            text("input_hello_message"),
            reply_markup=keyboards.back(data="AddHelloBack"),
        )
        return await state.set_state(Hello.message)


@safe_handler("Bots Choice Hello Message Delay")
async def choice_hello_message_delay(call: types.CallbackQuery, state: FSMContext):
    """Выбор задержки приветственного сообщения."""
    temp = call.data.split("|")
    data = await state.get_data()

    if temp[1] == "cancel":
        await call.message.delete()
        return await show_manage_hello_message(call.message, state)

    delay = int(temp[1])
    hello_message = await db.channel_bot_hello.update_hello_message(
        message_id=data.get("hello_message_id"), return_obj=True, delay=delay
    )

    await call.message.delete()
    await call.message.answer(
        text("application:delay"),
        reply_markup=keyboards.choice_hello_message_delay(current=hello_message.delay),
    )


@safe_handler("Bots Hello Back")
async def back(call: types.CallbackQuery, state: FSMContext):
    """Возврат в меню приветствий."""
    data = await state.get_data()
    await state.clear()
    await state.update_data(**data)

    await call.message.delete()

    if data.get("is_edit"):
        await call.message.answer(
            text("edit_hello"), reply_markup=keyboards.manage_hello_message_post()
        )
    else:
        cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))
        return await show_hello(call.message, cs)


@safe_handler("Bots Hello Get Message")
async def get_message(message: types.Message, state: FSMContext):
    """Обработка ввода приветственного сообщения."""
    message_text_length = len(message.caption or message.text or "")
    if message_text_length > 1024:
        return await message.answer(text("error_length_text"))

    dump_message = message.model_dump()
    if dump_message.get("photo"):
        dump_message["photo"] = Media(file_id=message.photo[-1].file_id)

    message_options = MessageOptionsHello(**dump_message)
    if message_text_length:
        if message_options.text:
            message_options.text = message.html_text
        if message_options.caption:
            message_options.caption = message.html_text

    data = await state.get_data()

    if data.get("is_edit"):
        await db.channel_bot_hello.update_hello_message(
            message_id=data.get("hello_message_id"),
            return_obj=True,
            message=message_options.model_dump(),
        )

        await message.bot.delete_message(message.from_user.id, data.get("post_id"))
        post_id = await answer_message(message, message_options)

        data.pop("post_id")
        await state.clear()
        await state.update_data(post_id=post_id.message_id, **data)

        return await message.answer(
            text("edit_hello"), reply_markup=keyboards.manage_hello_message_post()
        )

    else:
        next_id = await db.channel_bot_hello.get_next_id_hello_message()
        await db.channel_bot_hello.add_channel_hello_message(
            id=next_id,
            channel_id=data.get("chat_id"),
            message=message_options.model_dump(),
        )
        await state.update_data(hello_message_id=next_id)
        data = await state.get_data()

    await state.clear()
    await state.update_data(**data)

    await message.answer(text("success_add_hello"))

    cs = await db.channel_bot_settings.get_channel_bot_setting(data.get("chat_id"))
    await show_hello(message, cs)


@safe_handler("Bots Hello Get Buttons")
async def get_buttons(message: types.Message, state: FSMContext):
    """Обработка ввода кнопок для приветствия."""
    try:
        reply_markup = keyboards.hello_kb(message.text)
        r = await message.answer("...", reply_markup=reply_markup)
        await r.delete()
    except Exception as e:
        logger.error(f"Error parsing buttons: {e}", exc_info=True)
        return await message.answer(text("error_input"))

    data = await state.get_data()
    hello_obj = await db.channel_bot_hello.get_hello_message(
        message_id=data.get("hello_message_id")
    )

    hello_message = MessageOptionsHello(**hello_obj.message)
    hello_message.reply_markup = reply_markup

    await db.channel_bot_hello.update_hello_message(
        message_id=hello_obj.id, message=hello_message.model_dump()
    )

    await message.bot.delete_message(message.from_user.id, data.get("post_id"))
    post_id = await answer_message(message, hello_message)

    data.pop("post_id")
    await state.clear()
    await state.update_data(post_id=post_id.message_id, **data)

    await message.answer(
        text("edit_hello"), reply_markup=keyboards.manage_hello_message_post()
    )


def get_router():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ChoiceHelloMessage")
    router.callback_query.register(
        manage_hello_message, F.data.split("|")[0] == "ManageHelloMessage"
    )
    router.callback_query.register(
        choice_hello_message_delay, F.data.split("|")[0] == "ChoiceHelloMessageDelay"
    )
    router.callback_query.register(
        manage_hello_message_post, F.data.split("|")[0] == "ManagePostHelloMessage"
    )
    router.callback_query.register(back, F.data.split("|")[0] == "AddHelloBack")

    router.message.register(get_buttons, Hello.buttons, F.text)
    router.message.register(
        get_message, Hello.message, F.text | F.photo | F.video | F.animation
    )

    return router
