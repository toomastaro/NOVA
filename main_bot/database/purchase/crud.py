"""
Модуль операций базы данных для покупок.
"""

import logging

from sqlalchemy import insert, select

from main_bot.database import DatabaseMixin
from main_bot.database.purchase.model import Purchase

logger = logging.getLogger(__name__)


class PurchaseCrud(DatabaseMixin):
    """
    Класс для управления историей покупок.
    """

    async def add_purchase(self, **kwargs) -> None:
        """
        Добавляет запись о покупке.

        Аргументы:
            **kwargs: Поля модели Purchase.
        """
        await self.execute(insert(Purchase).values(**kwargs))

    async def has_purchase(self, user_id: int) -> Purchase | None:
        """
        Проверяет, совершал ли пользователь хотя бы одну покупку.

        Аргументы:
            user_id (int): ID пользователя.

        Возвращает:
            Purchase | None: Первая найденная покупка или None.
        """
        return await self.fetchrow(
            select(Purchase).where(Purchase.user_id == user_id).limit(1)
        )
