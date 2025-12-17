"""
Модуль операций базы данных для платежей.
"""

import logging

from sqlalchemy import insert

from main_bot.database import DatabaseMixin
from main_bot.database.payment.model import Payment

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
