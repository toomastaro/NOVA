"""
Модуль операций базы данных для NovaStat.
"""

import logging

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.novastat.model import (
    Collection,
    CollectionChannel,
    NovaStatSettings,
)

logger = logging.getLogger(__name__)


class NovaStatCrud(DatabaseMixin):
    """
    Класс для управления данными NovaStat (настройки, коллекции).
    """

    async def get_novastat_settings(self, user_id: int) -> NovaStatSettings:
        """
        Получает настройки пользователя. Если их нет - создает дефолтные.

        Аргументы:
            user_id (int): ID пользователя.

        Возвращает:
            NovaStatSettings: Объект настроек.
        """
        settings = await self.fetchrow(
            select(NovaStatSettings).where(NovaStatSettings.user_id == user_id)
        )
        if not settings:
            await self.execute(
                insert(NovaStatSettings).values(user_id=user_id, depth_days=7)
            )
            settings = await self.fetchrow(
                select(NovaStatSettings).where(NovaStatSettings.user_id == user_id)
            )
        return settings

    async def update_novastat_settings(self, user_id: int, **kwargs) -> None:
        """
        Обновляет настройки пользователя.
        """
        await self.execute(
            update(NovaStatSettings)
            .where(NovaStatSettings.user_id == user_id)
            .values(**kwargs)
        )

    async def get_collections(self, user_id: int) -> list[Collection]:
        """
        Получает список коллекций пользователя.

        Аргументы:
            user_id (int): ID пользователя.

        Возвращает:
            list[Collection]: Список коллекций.
        """
        return await self.fetch(select(Collection).where(Collection.user_id == user_id))

    async def get_collection(self, collection_id: int) -> Collection | None:
        """
        Получает коллекцию по ID.

        Аргументы:
            collection_id (int): ID коллекции.

        Возвращает:
            Collection | None: Объект коллекции.
        """
        # Eager load channels
        # Note: simple select might not load relationships eagerly without options,
        # but for now we'll fetch channels separately if needed or rely on lazy loading if session is open (which it isn't in this pattern)
        # Better to fetch channels explicitly
        return await self.fetchrow(
            select(Collection).where(Collection.id == collection_id)
        )

    async def get_collection_channels(self, collection_id: int) -> list[CollectionChannel]:
        """
        Получает список каналов в коллекции.
        """
        return await self.fetch(
            select(CollectionChannel).where(
                CollectionChannel.collection_id == collection_id
            )
        )

    async def create_collection(self, user_id: int, name: str) -> None:
        """
        Создает новую коллекцию.

        Аргументы:
            user_id (int): ID пользователя.
            name (str): Название коллекции.
        """
        await self.execute(insert(Collection).values(user_id=user_id, name=name))

    async def delete_collection(self, collection_id: int) -> None:
        """
        Удаляет коллекцию и все её каналы.
        """
        # Manually delete channels first because we use Core delete which bypasses ORM cascade
        await self.execute(
            delete(CollectionChannel).where(
                CollectionChannel.collection_id == collection_id
            )
        )
        await self.execute(delete(Collection).where(Collection.id == collection_id))

    async def rename_collection(self, collection_id: int, new_name: str) -> None:
        """
        Переименовывает коллекцию.
        """
        await self.execute(
            update(Collection)
            .where(Collection.id == collection_id)
            .values(name=new_name)
        )

    async def add_channel_to_collection(
        self, collection_id: int, channel_identifier: str
    ) -> None:
        """
        Добавляет канал в коллекцию.
        """
        await self.execute(
            insert(CollectionChannel).values(
                collection_id=collection_id, channel_identifier=channel_identifier
            )
        )

    async def remove_channel_from_collection(self, channel_id: int) -> None:
        """
        Удаляет канал из коллекции по ID записи.
        """
        await self.execute(
            delete(CollectionChannel).where(CollectionChannel.id == channel_id)
        )
