"""
Модуль для финансового отчета в админ-панели.
"""

import logging
import time
from datetime import datetime, timedelta

from aiogram import F, Router, types

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()


@safe_handler("Админ: Финансы — меню")
async def show_finance_menu(call: types.CallbackQuery) -> None:
    """Отображает главное меню финансового раздела."""
    active_subs = await db.channel.get_active_subscriptions_count()
    revenue_forecast = await db.channel.get_monthly_revenue_forecast()

    # Основная статистика
    text_msg = (
        "💰 <b>Финансовый раздел</b>\n\n"
        f"✅ <b>Активные подписки:</b> <code>{active_subs}</code>\n"
        f"📈 <b>Прогноз оборота (мес):</b> <code>{revenue_forecast:,}₽</code>\n"
        f"💵 <b>Средний чек:</b> <code>99₽</code>\n\n"
        "Выберите период для отчёта:"
    )

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text_msg,
            reply_markup=keyboards.admin_finance_menu(),
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await call.answer()


@safe_handler("Админ: Финансы — отчет")
async def show_finance_report(call: types.CallbackQuery) -> None:
    """
    Генерирует и показывает финансовый отчёт за выбранный период.
    """
    period = call.data.split("|")[2]
    now = datetime.now()
    
    start_ts = 0
    end_ts = int(time.time())
    period_name = "За всё время"

    if period == "today":
        start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_ts = int(start_date.timestamp())
        period_name = "Сегодня"
    elif period == "week":
        start_date = now - timedelta(days=7)
        start_ts = int(start_date.timestamp())
        period_name = "Последние 7 дней"
    elif period == "month":
        start_date = now - timedelta(days=30)
        start_ts = int(start_date.timestamp())
        period_name = "Последние 30 дней"

    # Получаем сводку платежей
    summary = await db.payment.get_payments_summary(start_ts, end_ts)
    
    total_count = 0
    total_sum = 0
    
    # Формируем текст
    text_msg = f"📊 <b>Отчёт: {period_name}</b>\n\n"
    
    payment_methods = {
        "STARS": "⭐️ Telegram Stars",
        "CRYPTO_BOT": "💎 CryptoBot",
        "PLATEGA": "💳 Platega",
        "BALANCE": "💰 Баланс"
    }

    if not summary:
        text_msg += "Платежей не найдено."
    else:
        for method, data in summary.items():
            method_name = payment_methods.get(method, method)
            count = data['count']
            amount = data['total']
            
            total_count += count
            total_sum += amount
            
            text_msg += (
                f"<b>{method_name}</b>\n"
                f"├ Платежей: {count}\n"
                f"└ Сумма: {amount:,}₽\n\n"
            )
            
        text_msg += (
            "━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>ИТОГО:</b> {total_count} платежей на <b>{total_sum:,}₽</b>"
        )

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text_msg,
            reply_markup=keyboards.admin_finance_menu(), # Оставляем меню для выбора другого периода
            parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await call.answer()


def get_router() -> Router:
    router.callback_query.register(
        show_finance_menu, F.data == "AdminFinance|menu"
    )
    router.callback_query.register(
        show_finance_report, F.data.startswith("AdminFinance|report")
    )
    return router
