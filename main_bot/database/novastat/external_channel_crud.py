"""
Модуль операций базы данных для внешних каналов NovaStat.
"""

import logging
import time
from typing import List, Optional

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from main_bot.database import DatabaseMixin
from main_bot.database.novastat.external_channel_model import ExternalChannel

logger = logging.getLogger(__name__)


class ExternalChannelCrud(DatabaseMixin):
    """
    Класс для управления внешними каналами (ExternalChannel).
    """

    async def get_external_channel(self, chat_id: int) -> Optional[ExternalChannel]:
        """Получить внешний канал по chat_id."""
        return await self.fetchrow(
            select(ExternalChannel).where(ExternalChannel.chat_id == chat_id)
        )

    async def get_by_username(self, username: str) -> Optional[ExternalChannel]:
        """Получить внешний канал по юзернейму."""
        # Убираем @ если есть
        clean_username = username.lstrip("@").lower()
        return await self.fetchrow(
            select(ExternalChannel).where(ExternalChannel.username.ilike(clean_username))
        )

    async def upsert_external_channel(self, **kwargs) -> None:
        """Добавить или обновить данные внешнего канала."""
        if "updated_at" not in kwargs:
            kwargs["updated_at"] = int(time.time())
        if "last_requested_at" not in kwargs:
            kwargs["last_requested_at"] = int(time.time())
            
        stmt = pg_insert(ExternalChannel).values(**kwargs)
        
        # При конфликте обновляем всё, кроме chat_id
        update_values = {k: v for k, v in kwargs.items() if k != "chat_id"}
        
        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id"],
            set_=update_values
        )
        await self.execute(stmt)

    async def mark_requested(self, chat_id: int) -> None:
        """Обновить время последнего запроса и активировать канал."""
        await self.execute(
            update(ExternalChannel)
            .where(ExternalChannel.chat_id == chat_id)
            .values(last_requested_at=int(time.time()), is_active=True)
        )

    async def get_active_for_update(self, interval_seconds: int = 10800) -> List[ExternalChannel]:
        """Получить список активных каналов, которые пора обновить (раз в 3 часа)."""
        cutoff = int(time.time()) - interval_seconds
        stmt = (
            select(ExternalChannel)
            .where(ExternalChannel.is_active)
            .where(ExternalChannel.updated_at < cutoff)
        )
        return await self.fetch(stmt)

    async def deactivate_old_channels(self, days: int = 14) -> int:
        """Деактивировать каналы, которые не запрашивались более N дней."""
        cutoff = int(time.time()) - (days * 86400)
        stmt = (
            update(ExternalChannel)
            .where(ExternalChannel.is_active)
            .where(ExternalChannel.last_requested_at < cutoff)
            .values(is_active=False)
            .returning(ExternalChannel.chat_id)
        )
        res = await self.fetch(stmt)
        return len(res)
