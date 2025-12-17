"""
Модуль операций базы данных для промокодов.
"""

import logging

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.promo.model import Promo

logger = logging.getLogger(__name__)


class PromoCrud(DatabaseMixin):
    """
    Класс для управления промокодами.
    """

    async def add_promo(self, **kwargs) -> None:
        """
        Добавляет новый промокод.

        Аргументы:
            **kwargs: Поля модели Promo.
        """
        await self.execute(insert(Promo).values(**kwargs))

    async def get_promo(self, name: str) -> Promo | None:
        """
        Получает промокод по имени.

        Аргументы:
            name (str): Код промокода.

        Возвращает:
            Promo | None: Объект промокода.
        """
        return await self.fetchrow(select(Promo).where(Promo.name == name))

    async def use_promo(self, promo: Promo) -> None:
        """
        Использует промокод (уменьшает счетчик или удаляет).

        Аргументы:
            promo (Promo): Объект промокода.
        """
        if promo.use_count == 1:
            stmt = delete(Promo).where(Promo.name == promo.name)
        else:
            stmt = (
                update(Promo)
                .where(Promo.name == promo.name)
                .values(use_count=promo.use_count - 1)
            )

        await self.execute(stmt)
