"""
Модуль для бизнес-аналитики в админ-панели.
"""

import logging

from aiogram import F, Router, types

from main_bot.database.db import db
from main_bot.keyboards import keyboards
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

router = Router()


@safe_handler("Админ: Аналитика — меню")
async def show_analytics_menu(call: types.CallbackQuery) -> None:
    """Главное меню аналитики"""
    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            "📈 <b>Бизнес-аналитика</b>\n\n"
            "Выберите раздел для просмотра детальной статистики.",
            reply_markup=keyboards.admin_analytics_menu(),
            parse_mode="HTML",
        )
    except TelegramBadRequest:
        pass

    await call.answer()


@safe_handler("Админ: Аналитика — сводка")
async def show_analytics_summary(call: types.CallbackQuery) -> None:
    """Сводка ключевых показателей (KPI)."""
    # Пользователи и воронка
    total_users = await db.user.get_total_users_count()
    users_with_channels = await db.user.get_users_with_channels_count()
    users_with_sub = await db.user.get_users_with_active_subscription_count()

    # Финансы
    total_revenue = await db.payment.get_total_revenue()
    active_subs = await db.channel.get_active_subscriptions_count()
    mrr = active_subs * 99  # Monthly Recurring Revenue (упрощенно)
    arr = mrr * 12  # Annual Recurring Revenue

    # Конверсии
    conv_channel = (users_with_channels / total_users * 100) if total_users else 0
    conv_sub = (
        (users_with_sub / users_with_channels * 100) if users_with_channels else 0
    )
    ltv = (total_revenue / total_users) if total_users else 0

    text_msg = (
        "📊 <b>Сводная статистика (KPI)</b>\n\n"
        "🎯 <b>Воронка пользователей:</b>\n"
        f"├ Всего пользователей: <b>{total_users}</b>\n"
        f"├ С каналами: <b>{users_with_channels}</b> ({conv_channel:.1f}%)\n"
        f"└ Платят (актив): <b>{users_with_sub}</b> ({conv_sub:.1f}% от каналов)\n\n"
        "💰 <b>Финансовые метрики:</b>\n"
        f"├ MRR (мес. доход): <b>{mrr:,}₽</b>\n"
        f"├ ARR (год. прогноз): <b>{arr:,}₽</b>\n"
        f"├ Средний LTV: <b>{ltv:.1f}₽</b>\n"
        f"└ Всего заработано: <b>{total_revenue:,}₽</b>"
    )

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text_msg, reply_markup=keyboards.admin_analytics_menu(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await call.answer()


@safe_handler("Админ: Аналитика — Churn & Retention")
async def show_analytics_churn(call: types.CallbackQuery) -> None:
    """Показатели оттока и удержания."""
    churn_rate = await db.channel.get_churn_rate(30)
    expired_30d = await db.channel.get_expired_subscriptions_count(30)
    avg_duration = await db.channel.get_average_subscription_duration()

    text_msg = (
        "📉 <b>Churn & Retention (30 дней)</b>\n\n"
        f"🚫 <b>Отток:</b>\n"
        f"├ Churn Rate: <b>{churn_rate}%</b>\n"
        f"└ Истекло подписок: <b>{expired_30d}</b>\n\n"
        f"⏳ <b>Удержание:</b>\n"
        f"└ Средняя жизнь подписки: <b>{avg_duration} дн.</b>"
    )

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text_msg, reply_markup=keyboards.admin_analytics_menu(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass

    await call.answer()


@safe_handler("Админ: Аналитика — Топ пользователей")
async def show_analytics_top(call: types.CallbackQuery) -> None:
    """Топ пользователей по каналам и платежам."""
    top_channels = await db.user.get_top_users_by_channels(5)
    top_payments = await db.payment.get_top_users_by_payments(5)

    text_msg = "🏆 <b>Топ пользователей</b>\n\n"

    text_msg += "📺 <b>По количеству каналов:</b>\n"
    for i, data in enumerate(top_channels, 1):
        user_link = f"<a href='tg://user?id={data['user_id']}'>{data['user_id']}</a>"
        text_msg += f"{i}. {user_link} — <b>{data['channels_count']}</b>\n"

    text_msg += "\n💰 <b>По сумме платежей:</b>\n"
    for i, data in enumerate(top_payments, 1):
        # Получим username для красоты, если есть (нужен отдельный запрос, пока по ID)
        user_link = f"<a href='tg://user?id={data['user_id']}'>{data['user_id']}</a>"
        text_msg += f"{i}. {user_link} — <b>{data['total_paid']:,}₽</b>\n"

    from aiogram.exceptions import TelegramBadRequest

    try:
        await call.message.edit_text(
            text_msg, reply_markup=keyboards.admin_analytics_menu(), parse_mode="HTML"
        )
    except TelegramBadRequest:
        pass  # Message is not modified

    await call.answer()


def get_router() -> Router:
    router.callback_query.register(show_analytics_menu, F.data == "AdminAnalytics|menu")
    router.callback_query.register(
        show_analytics_summary, F.data == "AdminAnalytics|summary"
    )
    router.callback_query.register(
        show_analytics_churn, F.data == "AdminAnalytics|churn"
    )
    router.callback_query.register(show_analytics_top, F.data == "AdminAnalytics|top")
    return router
