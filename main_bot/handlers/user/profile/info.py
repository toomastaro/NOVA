"""
Обработчики для раздела информации (политика конфиденциальности, пользовательское соглашение)
"""

from aiogram import Router, F, types

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler


@safe_handler(
    "Инфо: главное меню"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def show_info_menu(call: types.CallbackQuery):
    """Показать меню информации"""
    await call.message.answer(
        text("info:menu"), reply_markup=keyboards.info_menu(), parse_mode="HTML"
    )


@safe_handler(
    "Инфо: выбор раздела"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def choice(call: types.CallbackQuery):
    """Обработчик выбора в меню информации"""
    temp = call.data.split("|")

    if temp[1] == "back":
        # Возврат в меню подписки с информацией о балансе
        user = await db.user.get_user(user_id=call.from_user.id)
        await call.message.delete()
        return await call.message.answer(
            text("balance_text").format(user.balance),
            reply_markup=keyboards.subscription_menu(),
            parse_mode="HTML",
        )


def get_router():
    """Регистрация обработчиков"""
    router = Router()
    router.callback_query.register(choice, F.data.split("|")[0] == "InfoMenu")
    return router
