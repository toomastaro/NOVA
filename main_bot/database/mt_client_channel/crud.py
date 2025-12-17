"""
Модуль операций базы данных для связи клиентов и каналов.
"""

import logging
from typing import List, Optional

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.mt_client_channel.model import MtClientChannel

logger = logging.getLogger(__name__)


class MtClientChannelCrud(DatabaseMixin):
    """
    Класс для управления связями MtClient <-> Channel.
    """

    async def get_or_create_mt_client_channel(
        self, client_id: int, channel_id: int
    ) -> MtClientChannel:
        """
        Получает или создает запись о связи клиента и канала.

        Аргументы:
            client_id (int): ID клиента.
            channel_id (int): ID канала.

        Возвращает:
            MtClientChannel: Объект связи.
        """
        stmt = select(MtClientChannel).where(
            MtClientChannel.client_id == client_id,
            MtClientChannel.channel_id == channel_id,
        )
        obj = await self.fetchrow(stmt)

        if not obj:
            stmt = (
                insert(MtClientChannel)
                .values(client_id=client_id, channel_id=channel_id)
                .returning(MtClientChannel)
            )
            obj = await self.fetchrow(stmt, commit=True)

        return obj

    async def get_my_membership(self, channel_id: int) -> List[MtClientChannel]:
        """
        Получает список связей для конкретного канала (все клиенты в этом канале).

        Аргументы:
            channel_id (int): ID канала.
        """
        stmt = select(MtClientChannel).where(MtClientChannel.channel_id == channel_id)
        # Using fetch to return a list of items, as expected by handlers
        return await self.fetch(stmt)

    async def set_membership(self, client_id: int, channel_id: int, **kwargs) -> None:
        """
        Обновляет статус членства (и другие флаги) клиента в канале.

        Аргументы:
            client_id (int): ID клиента.
            channel_id (int): ID канала.
            **kwargs: Поля для обновления (is_member, is_admin, last_seen_at и т.д.).
        """
        # Filter allowed keys to avoid errors
        allowed_keys = {
            "is_member",
            "is_admin",
            "can_post_stories",
            "last_joined_at",
            "last_seen_at",
            "last_error_code",
            "last_error_at",
            "preferred_for_stats",
            "preferred_for_stories",
        }
        update_values = {k: v for k, v in kwargs.items() if k in allowed_keys}

        if not update_values:
            return

        await self.execute(
            update(MtClientChannel)
            .where(
                MtClientChannel.client_id == client_id,
                MtClientChannel.channel_id == channel_id,
            )
            .values(**update_values)
        )

    async def get_preferred_for_stats(
        self, channel_id: int
    ) -> Optional[MtClientChannel]:
        """
        Получает клиента, предпочтительного для сбора статистики в канале.
        """
        return await self.fetchrow(
            select(MtClientChannel)
            .where(
                MtClientChannel.channel_id == channel_id,
                MtClientChannel.preferred_for_stats,
            )
            .limit(1)
        )

    async def get_any_client_for_channel(
        self, channel_id: int
    ) -> Optional[MtClientChannel]:
        """
        Получает любого клиента, связанного с каналом.
        Используется как запасной вариант, если нет preferred client.
        """
        return await self.fetchrow(
            select(MtClientChannel)
            .where(MtClientChannel.channel_id == channel_id)
            .limit(1)
        )

    async def get_preferred_for_stories(
        self, channel_id: int
    ) -> Optional[MtClientChannel]:
        """
        Получает клиента, предпочтительного для постинга историй.
        """
        return await self.fetchrow(
            select(MtClientChannel)
            .where(
                MtClientChannel.channel_id == channel_id,
                MtClientChannel.preferred_for_stories,
            )
            .limit(1)
        )

    async def get_channels_by_client(self, client_id: int) -> list[MtClientChannel]:
        """
        Получает список всех каналов, с которыми связан клиент.
        """
        return await self.fetch(
            select(MtClientChannel).where(MtClientChannel.client_id == client_id)
        )

    async def delete_channels_by_client(self, client_id: int) -> None:
        """
        Удаляет все связи клиента с каналами.
        """

        await self.execute(
            delete(MtClientChannel).where(MtClientChannel.client_id == client_id)
        )
