"""
Обработчик команды /start.

Модуль отвечает за:
- Приветствие пользователя
- Обработку реферальных параметров (deep linking) для отслеживания рекламы
- Отображение версии бота (для администраторов)
"""

import logging

from aiogram import Router, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext

from config import Config
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler
from main_bot.utils.lang.language import text
from main_bot.utils.middlewares import StartMiddle

logger = logging.getLogger(__name__)


@safe_handler(
    "Команда: /start — начало работы"
)  # Безопасная обёртка: логирование + перехват ошибок без падения бота
async def start(message: types.Message, state: FSMContext) -> None:
    """
    Обработчик команды /start.
    Парсит реферальные параметры (ref_...) для трекинга конверсий.

    Аргументы:
        message (types.Message): Сообщение пользователя.
        state (FSMContext): Контекст состояния.
    """
    await state.clear()

    if message.text and len(message.text.split()) > 1:
        start_param = message.text.split()[1]

        if start_param.startswith("ref_"):
            try:
                params = start_param[4:]
                parts = params.split("_")

                if len(parts) >= 2:
                    purchase_id = int(parts[0])
                    slot_id = int(parts[1])

                    await db.ad_purchase.add_lead(
                        user_id=message.from_user.id,
                        ad_purchase_id=purchase_id,
                        slot_id=slot_id,
                        ref_param=start_param,
                    )
            except (ValueError, IndexError):
                pass

    is_admin = message.from_user.id in getattr(Config, "ADMINS", [])
    start_key = "start_text" if is_admin else "start_text_user"
    
    version_text = (
        f"Версия: {Config.VERSION}\n\n"
        if is_admin
        else ""
    )

    await message.answer(
        text(start_key) + f"\n\n{version_text}"
        f"📄 <a href='{text('info:terms:url')}'>{text('start:terms:text')}</a>\n"
        f"🔒 <a href='{text('info:privacy:url')}'>{text('start:privacy:text')}</a>",
        reply_markup=keyboards.menu(message.from_user.id),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


def get_router() -> Router:
    """
    Регистрирует обработчик команды /start и middleware.

    Возвращает:
        Router: Роутер с зарегистрированным хендлером старта.
    """
    router = Router()
    router.message.middleware(StartMiddle())
    router.message.register(start, CommandStart())
    return router
