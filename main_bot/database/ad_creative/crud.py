"""
Модуль операций базы данных для рекламных креативов.

Содержит класс `AdCreativeCrud` для создания, чтения и обновления
рекламных креативов и их ссылочных слотов.
"""

import logging

from sqlalchemy import insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.ad_creative.model import AdCreative, AdCreativeLinkSlot

logger = logging.getLogger(__name__)


class AdCreativeCrud(DatabaseMixin):
    """
    Класс для работы с таблицами ad_creatives и ad_creative_link_slots.
    """

    async def create_creative(self, **kwargs) -> int:
        """
        Создает новый рекламный креатив.

        Аргументы:
            **kwargs: Поля модели AdCreative (owner_id, name, raw_message, ...).

        Возвращает:
            int: ID созданного креатива.
        """
        query = insert(AdCreative).values(**kwargs).returning(AdCreative.id)
        return await self.fetchrow(query, commit=True)

    async def get_creative(self, creative_id: int) -> AdCreative | None:
        """
        Получает рекламный креатив по ID.

        Аргументы:
            creative_id (int): ID креатива.

        Возвращает:
            AdCreative | None: Объект креатива или None.
        """
        query = select(AdCreative).where(AdCreative.id == creative_id)
        return await self.fetchrow(query)

    async def get_user_creatives(self, owner_id: int) -> list[AdCreative]:
        """
        Получает список активных рекламных креативов пользователя.

        Исключает удаленные (status='deleted').

        Аргументы:
            owner_id (int): ID владельца.

        Возвращает:
            list[AdCreative]: Список креативов.
        """
        query = select(AdCreative).where(
            AdCreative.owner_id == owner_id, AdCreative.status != "deleted"
        )
        return await self.fetch(query)

    async def create_slots_for_creative(
        self, creative_id: int, slots: list[dict]
    ) -> None:
        """
        Создает слоты ссылок для креатива.

        Аргументы:
            creative_id (int): ID креатива.
            slots (list[dict]): Список словарей с данными слотов.
        """
        if not slots:
            return
        values = [{**slot, "creative_id": creative_id} for slot in slots]
        query = insert(AdCreativeLinkSlot).values(values)
        await self.execute(query)

    async def get_slots(self, creative_id: int) -> list[AdCreativeLinkSlot]:
        """
        Получает список слотов для креатива.

        Аргументы:
            creative_id (int): ID креатива.

        Возвращает:
            list[AdCreativeLinkSlot]: Список слотов.
        """
        query = select(AdCreativeLinkSlot).where(
            AdCreativeLinkSlot.creative_id == creative_id
        )
        return await self.fetch(query)

    async def update_creative_status(self, creative_id: int, status: str) -> None:
        """
        Обновляет статус креатива.

        Аргументы:
            creative_id (int): ID креатива.
            status (str): Новый статус (например, 'deleted', 'active').
        """
        query = (
            update(AdCreative).where(AdCreative.id == creative_id).values(status=status)
        )
        await self.execute(query)
