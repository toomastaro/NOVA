from typing import List, Optional
import time

from sqlalchemy import select, update, insert
from main_bot.database import DatabaseMixin
from main_bot.database.mt_client.model import MtClient


class MtClientCrud(DatabaseMixin):
    async def create_mt_client(self, **kwargs) -> MtClient:
        stmt = insert(MtClient).values(**kwargs).returning(MtClient)
        return await self.fetchrow(stmt, commit=True)

    async def get_mt_client(self, client_id: int) -> Optional[MtClient]:
        return await self.fetchrow(
            select(MtClient).where(MtClient.id == client_id)
        )

    async def get_mt_clients_by_pool(self, pool_type: str) -> List[MtClient]:
        return await self.fetch(
            select(MtClient).where(MtClient.pool_type == pool_type)
        )

    async def update_mt_client(self, client_id: int, **kwargs):
        await self.execute(
            update(MtClient).where(MtClient.id == client_id).values(**kwargs)
        )
