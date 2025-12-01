from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext


from hello_bot.database.db import Database
from hello_bot.handlers.user.menu import show_hello
from hello_bot.states.user import Hello
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import Media, MessageOptions, HelloAnswer
from hello_bot.utils.functions import answer_message


async def choice(call: types.CallbackQuery, state: FSMContext, db: Database, settings):
    temp = call.data.split('|')
    hello = HelloAnswer(**settings.hello)

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("start_text"),
            reply_markup=keyboards.menu()
        )

    if temp[1] in ["active", "message"]:
        if temp[1] == "active":
            hello.active = not hello.active
        if temp[1] == "message":
            if not hello.message:
                await call.message.edit_text(
                    text("input_hello_message"),
                    reply_markup=keyboards.back(
                        data="AddHelloBack"
                    )
                )
                return await state.set_state(Hello.message)

            if hello.message:
                hello.message = None
                hello.active = False

        if hello.active and not hello.message:
            return await call.answer(
                text("error:hello:add_message")
            )

        setting = await db.update_setting(
            return_obj=True,
            hello=hello.model_dump()
        )

        await call.message.delete()
        return await show_hello(call.message, setting)

    if temp[1] == "check":
        if not hello.message:
            return await call.answer(
                text("error:hello:add_message")
            )

        await call.message.delete()
        await answer_message(call.message, hello.message, None)
        await show_hello(call.message, settings)


async def back(call: types.CallbackQuery, state: FSMContext, settings):
    await state.clear()
    await call.message.delete()
    return await show_hello(call.message, settings)


async def get_message(message: types.Message, state: FSMContext, db: Database, settings):
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

    hello = HelloAnswer(**settings.hello)
    hello.message = message_options

    setting = await db.update_setting(
        return_obj=True,
        hello=hello.model_dump()
    )

    await state.clear()
    await message.answer(text("success_add_hello"))
    await show_hello(message, setting)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageHello")
    router.callback_query.register(back, F.data.split("|")[0] == "AddHelloBack")
    router.message.register(get_message, Hello.message, F.text | F.photo | F.video | F.animation)

    return router
