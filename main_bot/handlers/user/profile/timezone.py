"""
Модуль настройки часового пояса.
Позволяет пользователю установить свой часовой пояс для корректного отображения статистики и планировщика.
"""

from datetime import timedelta, datetime
import logging

from aiogram import types, Router, F
from aiogram.fsm.context import FSMContext

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.user import Setting
from main_bot.utils.lang.language import text
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


@safe_handler("Таймзона: получение")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def get_timezone(message: types.Message, state: FSMContext):
    """Обрабатывает ввод часового пояса от пользователя."""
    try:
        timezone_value = int(message.text.replace("+", ""))

        if timezone_value > 24:
            raise ValueError()
        if timezone_value < -24:
            raise ValueError()

    except ValueError:
        return await message.answer(
            text("error_input_timezone"),
            reply_markup=keyboards.back(data="InputTimezoneCancel"),
        )

    await db.user.update_user(user_id=message.from_user.id, timezone=timezone_value)

    await state.clear()

    # Показываем обновленное время
    delta = timedelta(hours=abs(timezone_value))
    if timezone_value > 0:
        new_timezone = datetime.utcnow() + delta
    else:
        new_timezone = datetime.utcnow() - delta

    await message.answer(
        f"✅ <b>Часовой пояс успешно обновлен!</b>\n\n"
        f"Ваш часовой пояс: <code>{'+' if timezone_value > 0 else ''}{timezone_value}</code>\n"
        f"Текущее время: <b>{new_timezone.strftime('%H:%M')}</b>",
        reply_markup=keyboards.back(data="InputTimezoneCancel"),
        parse_mode="HTML",
    )


@safe_handler("Таймзона: отмена")  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def cancel(call: types.CallbackQuery, state: FSMContext):
    """Отмена ввода часового пояса."""
    await state.clear()
    await call.message.delete()
    # Возврат в меню настроек (профиль)
    await call.message.answer(
        text("start_profile_text"),
        reply_markup=keyboards.profile_menu(),
        parse_mode="HTML",
    )


def get_router():
    """Регистрация роутеров часового пояса."""
    router = Router()
    router.message.register(get_timezone, Setting.input_timezone, F.text)
    router.callback_query.register(
        cancel, F.data.split("|")[0] == "InputTimezoneCancel"
    )
    return router
