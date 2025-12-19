"""
Обработчики баланса пользователя.
"""

import logging
from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Баланс: выбор действия")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery, state: FSMContext):
    """Маршрутизатор меню баланса."""
    temp = call.data.split("|")
    await call.message.delete()

    if temp[1] == "back":
        # Возврат в меню подписки с информацией о балансе
        user = await db.user.get_user(user_id=call.from_user.id)
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )

    if temp[1] == "top_up":
        await show_top_up(call.message, state)


@safe_handler("Баланс: меню пополнения")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_top_up(message: types.Message, state: FSMContext):
    """Показать методы пополнения баланса."""
    await state.update_data(payment_to="balance")
    await message.answer(
        text("choice_top_up_method"),
        reply_markup=keyboards.choice_payment_method(data="ChoicePaymentMethod"),
    )


def get_router():
    """Возвращает роутер для управления балансом."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Balance")
    return router
