"""
Модуль стартового меню администратора.

Содержит:
- Обработку команды /admin
- Главное меню панели администратора
- Навигацию по разделам (сессии, промокоды)
"""

import logging
import os

from aiogram import Router, F, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Админ: меню — команда /admin или /админ")
async def admin_menu(message: types.Message) -> None:
    """
    Показать главное меню администратора.
    Доступно только пользователям из списка Config.ADMINS.
    Команды: /admin, /админ
    """
    if message.from_user.id not in Config.ADMINS:
        return

    await message.answer(text("admin:menu:title"), reply_markup=keyboards.admin())


@safe_handler("Админ: меню — навигация")
async def choice(call: types.CallbackQuery, state: FSMContext) -> None:
    """
    Обработка нажатий в админ-меню.

    Аргументы:
        call (types.CallbackQuery): Callback запрос.
        state (FSMContext): Контекст состояния.
    """
    temp = call.data.split("|")
    action = temp[1]

    if action == "session":
        # Проверяем наличие директории сессий
        session_dir = "main_bot/utils/sessions/"
        session_count = 0
        if os.path.exists(session_dir):
            session_count = len(os.listdir(session_dir))

        try:
            await call.message.edit_text(
                text("admin:session:available").format(session_count),
                reply_markup=keyboards.admin_sessions(),
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing session message: {e}")
                raise

    elif action == "promo":
        await call.message.edit_text(
            text("admin:promo:input"),
            reply_markup=keyboards.back(data="AdminPromoBack"),
        )
        await state.set_state(Promo.input)

    elif action == "back":
        try:
            await call.message.edit_text(
                text("admin:menu:title"), reply_markup=keyboards.admin()
            )
        except Exception as e:
            if "message is not modified" not in str(e).lower():
                logger.error(f"Error editing back message: {e}")
                raise

    elif action == "stats":
        # TODO: Implement full stats logic
        try:
            await call.answer("Stats not implemented yet", show_alert=True)
        except Exception as e:
            logger.error(f"Error in stats: {e}")

    await call.answer()


def get_router() -> Router:
    """
    Регистрация роутера для админ-меню.

    Возвращает:
        Router: Роутер с зарегистрированными хендлерами.
    """
    router = Router()
    router.message.register(admin_menu, Command("admin"))
    router.message.register(admin_menu, Command("админ"))  # Русская команда
    router.callback_query.register(choice, F.data.split("|")[0] == "Admin")
    return router
