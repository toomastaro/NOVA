from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.handlers.user.profile.profile import show_setting
from main_bot.keyboards import keyboards
from main_bot.states.user import Setting
from main_bot.utils.lang.language import text


async def get_timezone(message: types.Message, state: FSMContext):
    try:
        timezone_value = int(message.text.replace("+", ""))

        if timezone_value > 24:
            raise ValueError()
        if timezone_value < -24:
            raise ValueError()

    except ValueError:
        return await message.answer(
            text('error_input_timezone'),
            reply_markup=keyboards.back(
                data='InputTimezoneCancel'
            )
        )

    await db.update_user(
        user_id=message.from_user.id,
        timezone=timezone_value
    )

    await state.clear()
    # Возврат в меню настроек (профиль)
    from main_bot.keyboards import keyboards
    from main_bot.utils.lang.language import text
    await message.answer(
        text('start_profile_text'),
        reply_markup=keyboards.profile_menu()
    )


async def cancel(call: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.delete()
    # Возврат в меню настроек (профиль)
    from main_bot.keyboards import keyboards
    from main_bot.utils.lang.language import text
    await call.message.answer(
        text('start_profile_text'),
        reply_markup=keyboards.profile_menu()
    )


def hand_add():
    router = Router()
    router.message.register(get_timezone, Setting.input_timezone, F.text)
    router.callback_query.register(cancel, F.data.split('|')[0] == 'InputTimezoneCancel')
    return router
