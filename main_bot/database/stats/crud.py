import logging
import time
from typing import Dict, Any

from sqlalchemy import func, select, insert

from main_bot.database import DatabaseMixin
from main_bot.database.payment.model import Payment
from main_bot.database.purchase.model import Purchase
from main_bot.database.user.model import User
from main_bot.database.stats.model import Stats

logger = logging.getLogger(__name__)


class StatsCrud(DatabaseMixin):
    """
    Класс для управления и получения статистики сервиса.
    """

    async def update_stats(self, **kwargs) -> None:
        """
        Обновляет статистику (добавляет новую запись).

        Аргументы:
            **kwargs: Поля модели Stats.
        """
        await self.execute(insert(Stats).values(**kwargs))

    async def get_admin_stats(self) -> Dict[str, Any]:
        """
        Собирает агрегированную статистику по пользователям и финансам.

        Возвращает:
            Dict[str, Any]: Словарь с метриками за разные периоды.
        """
        now = int(time.time())
        day = 24 * 3600
        week = 7 * day
        month = 30 * day

        stats = {}

        # 1. Счётчики пользователей
        stats["users_total"] = await self.fetchrow(select(func.count(User.id))) or 0
        stats["users_24h"] = (
            await self.fetchrow(
                select(func.count(User.id)).where(User.created_timestamp > now - day)
            )
            or 0
        )
        stats["users_7d"] = (
            await self.fetchrow(
                select(func.count(User.id)).where(User.created_timestamp > now - week)
            )
            or 0
        )
        stats["users_30d"] = (
            await self.fetchrow(
                select(func.count(User.id)).where(User.created_timestamp > now - month)
            )
            or 0
        )

        # 2. Финансы (Пополнения - Payments)
        stats["payments_total_sum"] = (
            await self.fetchrow(select(func.sum(Payment.amount))) or 0
        )
        stats["payments_total_count"] = (
            await self.fetchrow(select(func.count(Payment.id))) or 0
        )
        stats["payments_24h_sum"] = (
            await self.fetchrow(
                select(func.sum(Payment.amount)).where(
                    Payment.created_timestamp > now - day
                )
            )
            or 0
        )
        stats["payments_7d_sum"] = (
            await self.fetchrow(
                select(func.sum(Payment.amount)).where(
                    Payment.created_timestamp > now - week
                )
            )
            or 0
        )

        # 3. Финансы (Покупки - Purchases)
        stats["purchases_total_sum"] = (
            await self.fetchrow(select(func.sum(Purchase.amount))) or 0
        )
        stats["purchases_total_count"] = (
            await self.fetchrow(select(func.count(Purchase.id))) or 0
        )
        stats["purchases_24h_sum"] = (
            await self.fetchrow(
                select(func.sum(Purchase.amount)).where(
                    Purchase.created_timestamp > now - day
                )
            )
            or 0
        )
        stats["purchases_7d_sum"] = (
            await self.fetchrow(
                select(func.sum(Purchase.amount)).where(
                    Purchase.created_timestamp > now - week
                )
            )
            or 0
        )

        return stats
