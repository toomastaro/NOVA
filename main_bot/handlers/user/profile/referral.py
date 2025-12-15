"""
Модуль обработки реферальной программы в профиле.
"""
from aiogram import types, Router, F

from main_bot.handlers.user.menu import profile
from main_bot.utils.error_handler import safe_handler


@safe_handler("Referral Choice")
async def choice(call: types.CallbackQuery):
    """Обработчик действий в меню реферальной программы."""
    temp = call.data.split('|')
    await call.message.delete()

    if temp[1] == 'back':
        # Возврат в меню подписки с информацией о балансе
        from main_bot.database.db import db
        from main_bot.keyboards import keyboards
        from main_bot.utils.lang.language import text
        
        user = await db.user.get_user(user_id=call.from_user.id)
        await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML"
        )


def get_router():
    """Регистрация роутера реферальной системы."""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "Referral")
    return router
