"""
Модуль операций базы данных для рекламных тегов.
"""

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.ad_tag.model import AdTag


class AdTagCrud(DatabaseMixin):
    """
    Класс для управления рекламными тегами (AdTag).
    """

    async def add_ad_tag(self, **kwargs) -> None:
        """
        Создает новый рекламный тег.

        Аргументы:
            **kwargs: Поля модели AdTag.
        """
        await self.execute(insert(AdTag).values(**kwargs))

    async def remove_ad_tag(self, name: str) -> None:
        """
        Удаляет тег по имени.

        Аргументы:
            name (str): Название тега.
        """
        await self.execute(delete(AdTag).where(AdTag.name == name))

    async def get_ad_tag(self, name: str) -> AdTag | None:
        """
        Получает тег по имени.

        Аргументы:
            name (str): Название тега.

        Возвращает:
            AdTag | None: Объект тега или None.
        """
        return await self.fetchrow(select(AdTag).where(AdTag.name == name))

    async def update_ad_tag(self, name: str, **kwargs) -> None:
        """
        Обновляет поля тега.

        Аргументы:
            name (str): Название тега.
            **kwargs: Поля для обновления.
        """
        await self.execute(update(AdTag).where(AdTag.name == name).values(**kwargs))
