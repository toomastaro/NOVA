"""
Модуль операций базы данных для курсов валют.
"""

import logging

from sqlalchemy import insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.exchange_rate.model import ExchangeRate

logger = logging.getLogger(__name__)


class ExchangeRateCrud(DatabaseMixin):
    """
    Класс для управления курсами валют.
    """

    async def get_all_exchange_rate(self) -> list:
        """
        Получает все курсы валют.
        """
        return await self.fetch(select(ExchangeRate))

    async def get_exchange_rate(self, exchange_rate_id: int) -> ExchangeRate | None:
        """
        Получает курс валюты по ID.
        """
        return await self.fetchrow(
            select(ExchangeRate).where(ExchangeRate.id == exchange_rate_id)
        )

    async def add_exchange_rate(self, **kwargs) -> None:
        """
        Добавляет новый курс валюты.

        Аргументы:
            **kwargs: Поля модели ExchangeRate.
        """
        await self.execute(insert(ExchangeRate).values(**kwargs))

    async def update_exchange_rate(
        self, exchange_rate_id: int, return_obj: bool = False, **kwargs
    ) -> ExchangeRate | None:
        """
        Обновляет курс валюты.

        Аргументы:
            exchange_rate_id (int): ID курса.
            return_obj (bool): Вернуть ли обновленный объект.
            **kwargs: Поля для обновления.
        """
        stmt = (
            update(ExchangeRate)
            .where(ExchangeRate.id == exchange_rate_id)
            .values(**kwargs)
        )

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ExchangeRate)
        else:
            operation = self.execute
        return await operation(stmt, **{"commit": return_obj} if return_obj else {})
