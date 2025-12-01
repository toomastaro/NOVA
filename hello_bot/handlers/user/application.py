from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext


from hello_bot.database.db import Database
from hello_bot.handlers.user.menu import show_application
from hello_bot.states.user import Application
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import Protect


async def choice(call: types.CallbackQuery, state: FSMContext, db: Database, settings):
    temp = call.data.split('|')
    protect = Protect(**settings.protect)

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("start_text"),
            reply_markup=keyboards.menu()
        )

    if temp[1] in ["protect_arab", "protect_china", "auto_approve"]:
        if temp[1] == "protect_arab":
            protect.arab = not protect.arab
        if temp[1] == "protect_china":
            protect.china = not protect.china
        if temp[1] == "auto_approve":
            settings.auto_approve = not settings.auto_approve

        settings = await db.update_setting(
            return_obj=True,
            protect=protect.model_dump(),
            auto_approve=settings.auto_approve
        )

        await call.message.delete()
        return await show_application(call.message, settings)

    if temp[1] == "delay_approve":
        await call.message.edit_text(
            text("input_delay_approve"),
            reply_markup=keyboards.back(
                data="AddDelayBack"
            )
        )
        await state.set_state(Application.delay)


async def back(call: types.CallbackQuery, state: FSMContext, settings):
    await state.clear()
    await call.message.delete()
    return await show_application(call.message, settings)


async def get_message(message: types.Message, state: FSMContext, db: Database):
    try:
        delay = int(message.text)
    except ValueError:
        return await message.answer(
            text('error_input')
        )

    settings = await db.update_setting(
        return_obj=True,
        delay_approve=delay
    )

    await state.clear()
    await show_application(message, settings)


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageApplication")
    router.callback_query.register(back, F.data.split("|")[0] == "AddDelayBack")
    router.message.register(get_message, Application.delay, F.text)

    return router
