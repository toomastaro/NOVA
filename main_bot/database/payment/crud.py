"""
Модуль операций базы данных для платежей.
"""

import logging
from typing import Dict, List, Optional

from sqlalchemy import func, insert, select

from main_bot.database import DatabaseMixin
from main_bot.database.payment.model import Payment
from main_bot.database.db_types import PaymentMethod

logger = logging.getLogger(__name__)


class PaymentCrud(DatabaseMixin):
    """
    Класс для управления историей платежей.
    """

    async def add_payment(self, **kwargs) -> None:
        """
        Создает запись о платеже.

        Аргументы:
            **kwargs: Поля модели Payment.
        """
        await self.execute(insert(Payment).values(**kwargs))

    async def get_payments_by_period(
        self,
        start_ts: int,
        end_ts: int,
        method: Optional[PaymentMethod] = None,
    ) -> List[Payment]:
        """
        Получить платежи за период с опциональным фильтром по методу.

        Аргументы:
            start_ts (int): Начало периода (timestamp).
            end_ts (int): Конец периода (timestamp).
            method (PaymentMethod | None): Метод оплаты для фильтрации.

        Возвращает:
            List[Payment]: Список платежей.
        """
        stmt = select(Payment).where(
            Payment.created_timestamp >= start_ts, Payment.created_timestamp <= end_ts
        )
        if method:
            stmt = stmt.where(Payment.method == method)
        return await self.fetch(stmt)

    async def get_payments_summary(
        self, start_ts: int, end_ts: int
    ) -> Dict[str, Dict[str, int]]:
        """
        Получить сводку платежей по методам оплаты за период.
        Агрегирует данные из таблиц payments (пополнения) и purchases (прямые покупки).
        Исключает покупки с методом BALANCE из таблицы purchases, так как они уже учтены в пополнениях.

        Аргументы:
            start_ts (int): Начало периода (timestamp).
            end_ts (int): Конец периода (timestamp).

        Возвращает:
            Dict[str, Dict[str, int]]: Сводка вида:
                {
                    'STARS': {'count': 15, 'total': 1485},
                    'CRYPTO_BOT': {'count': 8, 'total': 792},
                    ...
                }
        """
        from main_bot.database.purchase.model import Purchase

        # 1. Получаем пополнения (Top-ups)
        stmt_payments = (
            select(
                Payment.method.label("payment_method"),
                func.count(Payment.id).label("payments_count"),
                func.sum(Payment.amount).label("total_amount"),
            )
            .where(
                Payment.created_timestamp >= start_ts,
                Payment.created_timestamp <= end_ts,
            )
            .group_by(Payment.method)
        )

        payments_result = await self.fetchall(stmt_payments)
        
        # 2. Получаем прямые покупки (Direct Purchases), исключая оплату с баланса
        stmt_purchases = (
            select(
                Purchase.method.label("payment_method"),
                func.count(Purchase.id).label("payments_count"),
                func.sum(Purchase.amount).label("total_amount"),
            )
            .where(
                Purchase.created_timestamp >= start_ts,
                Purchase.created_timestamp <= end_ts,
                Purchase.method != PaymentMethod.BALANCE
            )
            .group_by(Purchase.method)
        )

        purchases_result = await self.fetchall(stmt_purchases)

        # 3. Объединяем результаты
        summary = {}

        for row in payments_result:
            method = str(row.payment_method)
            summary[method] = {
                "count": row.payments_count,
                "total": int(row.total_amount or 0)
            }

        for row in purchases_result:
            method = str(row.payment_method)
            if method not in summary:
                summary[method] = {"count": 0, "total": 0}
            
            summary[method]["count"] += row.payments_count
            summary[method]["total"] += int(row.total_amount or 0)

        return summary

    async def get_total_payments_count(self) -> int:
        """
        Получить общее количество платежей за всё время.

        Возвращает:
            int: Количество платежей.
        """
        result = await self.fetchrow(select(func.count(Payment.id)))
        return result if result else 0

    async def get_total_revenue(self) -> int:
        """
        Получить общую сумму всех платежей за всё время.

        Возвращает:
            int: Общая сумма в рублях.
        """
        result = await self.fetchrow(select(func.sum(Payment.amount)))
        return int(result) if result else 0

    async def get_top_users_by_payments(self, limit: int = 10) -> List[Dict]:
        """
        Получить топ пользователей по сумме платежей.

        Аргументы:
            limit (int): Количество пользователей в топе.

        Возвращает:
            List[Dict]: Список вида [{'user_id': 123, 'total_paid': 990}, ...]
        """
        stmt = (
            select(
                Payment.user_id, func.sum(Payment.amount).label("total_paid")
            )
            .group_by(Payment.user_id)
            .order_by(func.sum(Payment.amount).desc())
            .limit(limit)
        )

        result = await self.fetchall(stmt)
        return [
            {"user_id": row.user_id, "total_paid": int(row.total_paid)}
            for row in result
        ]
