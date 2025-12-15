import logging
import os

from aiogram import types, Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo
from main_bot.utils.lang.language import text

logger = logging.getLogger(__name__)


async def admin_menu(message: types.Message):
    if message.from_user.id not in Config.ADMINS:
        return

    await message.answer(
        text('admin:menu:title'),
        reply_markup=keyboards.admin()
    )


async def choice(call: types.CallbackQuery, state: FSMContext):
    """Обработка нажатий в админ-меню."""
    temp = call.data.split('|')
    action = temp[1]

    if action == 'session':
        session_count = len(os.listdir("main_bot/utils/sessions/"))
        try:
            await call.message.edit_text(
                text('admin:session:available').format(session_count),
                reply_markup=keyboards.admin_sessions()
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing session message: {e}")
                raise

    elif action == "promo":
        await call.message.edit_text(
            text('admin:promo:input'),
            reply_markup=keyboards.back(
                data="AdminPromoBack"
            )
        )
        await state.set_state(Promo.input)

    elif action == "back":
        try:
            await call.message.edit_text(
                text('admin:menu:title'),
                reply_markup=keyboards.admin()
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing back message: {e}")
                raise

    elif action == "stats":
         # TODO: Implement full stats logic
         # Currently just a placeholder based on existing code structure
        try:
            # Need to implement data gathering for stats first
             await call.answer("Stats not implemented yet", show_alert=True)
            # await call.message.edit_text(
            #     text("main:stats").format(...)
            # )
        except Exception as e:
             logger.error(f"Error in stats: {e}")

    # Dead code removed (mail, ads placeholders were empty or unreachable)
    
    return await call.answer()


def get_router():
    """Регистрация роутера для админ-меню."""
    router = Router()
    router.message.register(admin_menu, Command('admin'))
    router.callback_query.register(choice, F.data.split('|')[0] == "Admin")
    return router
