"""
Модуль для возврата из статистики (stats).

Обрабатывает кнопку "Назад" в разделе статистики.
"""

from aiogram import types, F, Router
from loguru import logger

from hello_bot.utils.lang.language import text
from hello_bot.keyboards.keyboards import keyboards
from utils.error_handler import safe_handler


@safe_handler("Статистика: возврат")
async def choice(call: types.CallbackQuery):
    """
    Возврат в главное меню из статистики.

    :param call: CallbackQuery
    """
    logger.debug(f"Возврат из статистики: {call.data}")
    await call.message.edit_text(text("start_text"), reply_markup=keyboards.menu())


def hand_add():
    """Регистрация хэндлеров статистики."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "StatsBack")
    return router
