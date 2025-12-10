from datetime import timedelta, datetime

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.database.user.model import User
from main_bot.handlers.user.menu import profile
from main_bot.keyboards import keyboards
from main_bot.states.user import Setting
from main_bot.utils.lang.language import text


async def choice(call: types.CallbackQuery, state: FSMContext, user: User):
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'back':
        await profile(call.message)

    if temp[1] == 'folders':
        await show_folders(call.message)

    if temp[1] == 'report_settings':
        from main_bot.handlers.user.profile.report_settings import show_report_settings_menu
        await show_report_settings_menu(call)

    if temp[1] == 'timezone':
        delta = timedelta(hours=abs(user.timezone))

        if user.timezone > 0:
            timezone = datetime.utcnow() + delta
        else:
            timezone = datetime.utcnow() - delta

        await call.message.answer(
            text('input_timezone').format(
                f"+{user.timezone}" if user.timezone > 0 else user.timezone,
                timezone.strftime('%H:%M')
            ),
            reply_markup=keyboards.back(
                data='InputTimezoneCancel'
            )
        )
        await state.set_state(Setting.input_timezone)


async def show_timezone(message: types.Message):
    """Показать меню настройки часового пояса"""
    from main_bot.database.db import db
    from datetime import timedelta, datetime
    from aiogram.fsm.context import FSMContext
    
    user = await db.get_user(user_id=message.chat.id)
    delta = timedelta(hours=abs(user.timezone))

    if user.timezone > 0:
        timezone = datetime.utcnow() + delta
    else:
        timezone = datetime.utcnow() - delta

    await message.answer(
        text('input_timezone').format(
            f"+{user.timezone}" if user.timezone > 0 else user.timezone,
            timezone.strftime('%H:%M')
        ),
        reply_markup=keyboards.back(
            data='InputTimezoneCancel'
        )
    )


async def show_folders(message: types.Message):
    folders = await db.get_folders(message.chat.id)

    await message.answer(
        text('folders_text'),
        reply_markup=keyboards.folders(
            folders=folders
        )
    )


def hand_add():
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Setting")
    return router
