"""
Модуль управления заявками (application).

Позволяет настраивать автоприем заявок, защиту от ботов (арабских/китайских) и задержку одобрения.
"""

from aiogram import types, F, Router
from aiogram.fsm.context import FSMContext
from loguru import logger


from hello_bot.database.db import Database
from hello_bot.handlers.user.menu import show_application
from hello_bot.states.user import Application
from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from hello_bot.utils.schemas import Protect
from utils.error_handler import safe_handler


@safe_handler("Заявки: выбор действия")
async def choice(call: types.CallbackQuery, state: FSMContext, db: Database, settings):
    """
    Обрабатывает выбор действия в меню заявок.

    :param call: CallbackQuery
    :param state: FSMContext
    :param db: Database instance
    :param settings: Channel settings
    """
    temp = call.data.split("|")
    protect = Protect(**settings.protect)
    logger.debug(f"Выбор в заявках: {temp}")

    if temp[1] == "cancel":
        return await call.message.edit_text(
            text("start_text"), reply_markup=keyboards.menu()
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
            auto_approve=settings.auto_approve,
        )
        logger.info(
            f"Настройки заявок обновлены: авто_одобрение={settings.auto_approve}, защита={protect.model_dump()}"
        )

        await call.message.delete()
        return await show_application(call.message, settings)

    if temp[1] == "delay_approve":
        await call.message.edit_text(
            text("input_delay_approve"),
            reply_markup=keyboards.back(data="AddDelayBack"),
        )
        await state.set_state(Application.delay)


async def back(call: types.CallbackQuery, state: FSMContext, settings):
    """Возврат назад."""
    await state.clear()
    await call.message.delete()
    return await show_application(call.message, settings)


@safe_handler("Заявки: установка задержки")
async def get_message(message: types.Message, state: FSMContext, db: Database):
    """
    Обрабатывает ввод задержки одобрения заявок.
    """
    try:
        delay = int(message.text)
    except ValueError:
        return await message.answer(text("error_input"))

    settings = await db.update_setting(return_obj=True, delay_approve=delay)
    logger.info(f"Задержка одобрения обновлена до {delay}")

    await state.clear()
    await show_application(message, settings)


def hand_add():
    """Регистрация хэндлеров для заявок."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "ManageApplication")
    router.callback_query.register(back, F.data.split("|")[0] == "AddDelayBack")
    router.message.register(get_message, Application.delay, F.text)

    return router
