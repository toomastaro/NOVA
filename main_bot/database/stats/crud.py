"""
Модуль операций базы данных для статистики.
"""

import logging

from sqlalchemy import insert

from main_bot.database import DatabaseMixin
from main_bot.database.stats.model import Stats

logger = logging.getLogger(__name__)


class StatsCrud(DatabaseMixin):
    """
    Класс для управления статистикой.
    """

    async def update_stats(self, **kwargs) -> None:
        """
        Обновляет статистику (добавляет новую запись).

        Аргументы:
            **kwargs: Поля модели Stats.
        """
        await self.execute(insert(Stats).values(**kwargs))
