"""
Модуль операций базы данных для MTProto клиентов.
"""

import logging
import time
from typing import List, Optional

from sqlalchemy import insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.mt_client.model import MtClient

logger = logging.getLogger(__name__)


class MtClientCrud(DatabaseMixin):
    """
    Класс для управления MTProto клиентами (MtClient).
    """

    async def create_mt_client(self, **kwargs) -> MtClient | None:
        """
        Создает нового MTProto клиента.

        Аргументы:
            **kwargs: Поля модели MtClient.

        Возвращает:
            MtClient | None: Созданный клиент.
        """
        stmt = insert(MtClient).values(**kwargs).returning(MtClient)
        return await self.fetchrow(stmt, commit=True)

    async def get_mt_client(self, client_id: int) -> Optional[MtClient]:
        """
        Получает клиента по ID.
        """
        return await self.fetchrow(select(MtClient).where(MtClient.id == client_id))

    async def get_mt_clients_by_pool(self, pool_type: str) -> List[MtClient]:
        """
        Получает список клиентов по типу пула ('internal', 'external' или 'unassigned').

        Аргументы:
            pool_type (str): Тип пула.
        """
        return await self.fetch(
            select(MtClient)
            .where(MtClient.pool_type == pool_type)
            .order_by(MtClient.alias.asc())
        )

    async def update_mt_client(self, client_id: int, **kwargs) -> None:
        """
        Обновляет данные клиента.

        Аргументы:
            client_id (int): ID клиента.
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(MtClient).where(MtClient.id == client_id).values(**kwargs)
        )

    async def get_next_internal_client(self, chat_id: int) -> Optional[MtClient]:
        """
        Получает наименее загруженного (Least Used) internal клиента для канала.

        Вместо round-robin (который вызывал перегрузку первого клиента),
        теперь выбирается клиент с наименьшим количеством назначенных каналов.

        Аргументы:
            chat_id (int): Telegram ID канала (не используется в выборке, но оставлен для совместимости).

        Возвращает:
            MtClient | None: Internal клиент с наименьшей нагрузкой.
        """
        from sqlalchemy import func
        from main_bot.database.mt_client_channel.model import MtClientChannel

        # Выбираем клиента с наименьшим количеством записей в mt_client_channels
        stmt = (
            select(MtClient)
            .outerjoin(MtClientChannel, MtClientChannel.client_id == MtClient.id)
            .where(
                MtClient.pool_type == "internal",
                MtClient.is_active,
                MtClient.status == "ACTIVE",
            )
            .group_by(MtClient.id)
            # Сортируем по количеству каналов (возрастание) и ID (для стабильности)
            .order_by(func.count(MtClientChannel.id).asc(), MtClient.id.asc())
            .limit(1)
        )

        return await self.fetchrow(stmt)

    async def get_next_external_client(self) -> Optional[MtClient]:
        """
        Получает наименее используемого external клиента (least-used алгоритм).

        Возвращает:
            MtClient | None: External клиент с наименьшим usage_count или None если нет активных.
        """
        # Получить всех активных external клиентов, отсортированных по usage_count
        clients = await self.fetch(
            select(MtClient)
            .where(MtClient.pool_type == "external")
            .where(MtClient.is_active)
            .where(MtClient.status == "ACTIVE")
            .order_by(MtClient.usage_count.asc(), MtClient.last_used_at.asc())
        )

        if not clients:
            return None

        # Вернуть первого (наименее используемого)
        return clients[0]

    async def increment_usage(self, client_id: int) -> None:
        """
        Увеличивает счетчик использования клиента.

        Аргументы:
            client_id (int): ID клиента.
        """
        await self.execute(
            update(MtClient)
            .where(MtClient.id == client_id)
            .values(usage_count=MtClient.usage_count + 1, last_used_at=int(time.time()))
        )
