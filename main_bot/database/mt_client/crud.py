import time
from typing import List, Optional

from main_bot.database import DatabaseMixin
from main_bot.database.mt_client.model import MtClient
from sqlalchemy import insert, select, update


class MtClientCrud(DatabaseMixin):
    async def create_mt_client(self, **kwargs) -> MtClient:
        stmt = insert(MtClient).values(**kwargs).returning(MtClient)
        return await self.fetchrow(stmt, commit=True)

    async def get_mt_client(self, client_id: int) -> Optional[MtClient]:
        return await self.fetchrow(select(MtClient).where(MtClient.id == client_id))

    async def get_mt_clients_by_pool(self, pool_type: str) -> List[MtClient]:
        return await self.fetch(select(MtClient).where(MtClient.pool_type == pool_type))

    async def update_mt_client(self, client_id: int, **kwargs):
        await self.execute(
            update(MtClient).where(MtClient.id == client_id).values(**kwargs)
        )

    async def get_next_internal_client(self, channel_id: int) -> Optional[MtClient]:
        """
        Получить следующего internal клиента для канала по алгоритму round-robin.

        Args:
            channel_id: ID канала

        Returns:
            Следующий internal клиент или None если нет активных
        """
        # Получить всех активных internal клиентов
        clients = await self.fetch(
            select(MtClient)
            .where(MtClient.pool_type == "internal")
            .where(MtClient.is_active)
            .where(MtClient.status == "ACTIVE")
            .order_by(MtClient.id)  # Стабильный порядок
        )

        if not clients:
            return None

        # Получить last_client_id канала
        from main_bot.database.channel.model import Channel

        channel = await self.fetchrow(select(Channel).where(Channel.id == channel_id))

        if not channel or not channel.last_client_id:
            # Первый раз - вернуть первого клиента
            return clients[0]

        # Найти индекс последнего использованного клиента
        client_ids = [c.id for c in clients]
        try:
            last_index = client_ids.index(channel.last_client_id)
            # Взять следующего по кругу
            next_index = (last_index + 1) % len(clients)
        except ValueError:
            # Последний клиент больше не активен - начать с первого
            next_index = 0

        return clients[next_index]

    async def get_next_external_client(self) -> Optional[MtClient]:
        """
        Получить наименее используемого external клиента (least-used алгоритм).

        Returns:
            External клиент с наименьшим usage_count или None если нет активных
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

    async def increment_usage(self, client_id: int):
        """
        Увеличить счетчик использования клиента.

        Args:
            client_id: ID клиента
        """
        await self.execute(
            update(MtClient)
            .where(MtClient.id == client_id)
            .values(usage_count=MtClient.usage_count + 1, last_used_at=int(time.time()))
        )
