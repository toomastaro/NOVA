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
from main_bot.database.db import db
from main_bot.keyboards import keyboards
from main_bot.states.admin import Promo, AdminMailing
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

    elif action == "mail":
        await call.message.edit_text(
            text("admin:mailing:input"),
            reply_markup=keyboards.back(data="Admin|back"),
            parse_mode="HTML"
        )
        await state.set_state(AdminMailing.post)

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
        """
        Отображение статистики сервиса.
        Показывает данные по пользователям, пополнениям и покупкам.
        """
        try:
            stats = await db.stats.get_admin_stats()
            
            stats_text = (
                "📊 <b>СТАТИСТИКА СЕРВИСА</b>\n\n"
                "👤 <b>Пользователи:</b>\n"
                f"├ Всего: <code>{stats['users_total']}</code>\n"
                f"├ За 30 дней: <code>+{stats['users_30d']}</code>\n"
                f"├ За 7 дней: <code>+{stats['users_7d']}</code>\n"
                f"└ За 24 часа: <code>+{stats['users_24h']}</code>\n\n"
                
                "💰 <b>Финансы (Пополнения):</b>\n"
                f"├ Всего: <code>{stats['payments_total_sum']:,}₽</code> ({stats['payments_total_count']} транз.)\n"
                f"├ За 7 дней: <code>{stats['payments_7d_sum']:,}₽</code>\n"
                f"└ За 24 часа: <code>{stats['payments_24h_sum']:,}₽</code>\n\n"
                
                "🛍 <b>Финансы (Покупки услуг):</b>\n"
                f"├ Всего: <code>{stats['purchases_total_sum']:,}₽</code> ({stats['purchases_total_count']} оплат)\n"
                f"├ За 7 дней: <code>{stats['purchases_7d_sum']:,}₽</code>\n"
                f"└ За 24 часа: <code>{stats['purchases_24h_sum']:,}₽</code>\n\n"
                
                "<i>* Статистика обновляется в реальном времени</i>"
            )
            
            await call.message.edit_text(
                stats_text,
                reply_markup=keyboards.back(data="Admin|back"),
                parse_mode="HTML"
            )
        except Exception as e:
            logger.error(f"Error in stats: {e}", exc_info=True)
            await call.answer("❌ Ошибка при получении статистики", show_alert=True)

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
