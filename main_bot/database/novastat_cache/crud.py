"""
Модуль операций базы данных для кэша NovaStat.
"""

import logging
import time
from typing import Optional

from sqlalchemy import select, update

from main_bot.database import DatabaseMixin
from main_bot.database.novastat_cache.model import NovaStatCache

logger = logging.getLogger(__name__)


class NovaStatCacheCrud(DatabaseMixin):
    """
    Класс для управления кэшем статистики каналов (NovaStat).
    """

    async def get_cache(
        self, channel_identifier: str, horizon: int
    ) -> Optional[NovaStatCache]:
        """
        Получает кэш для канала и временного горизонта.

        Аргументы:
            channel_identifier (str): Идентификатор канала.
            horizon (int): Кэшируемый период (24, 48, 72).

        Возвращает:
            NovaStatCache | None: Объект кэша.
        """
        stmt = select(NovaStatCache).where(
            NovaStatCache.channel_identifier == channel_identifier,
            NovaStatCache.horizon == horizon,
        )
        result = await self.fetch(stmt)
        return result[0] if result else None

    async def is_cache_fresh(
        self, channel_identifier: str, horizon: int, max_age_seconds: int = 3600
    ) -> bool:
        """
        Проверяет, свежий ли кэш (по умолчанию 60 минут).

        Аргументы:
            channel_identifier (str): Идентификатор канала.
            horizon (int): Горизонт.
            max_age_seconds (int): Максимальный возраст кэша в секундах.

        Возвращает:
            bool: True, если кэш свежий.
        """
        cache = await self.get_cache(channel_identifier, horizon)
        if not cache:
            return False

        current_time = int(time.time())
        age = current_time - cache.updated_at
        return age < max_age_seconds

    async def set_cache(
        self,
        channel_identifier: str,
        horizon: int,
        value_json: dict,
        error_message: Optional[str] = None,
    ) -> NovaStatCache:
        """
        Создает или обновляет запись кэша.

        Аргументы:
            channel_identifier (str): Идентификатор канала.
            horizon (int): Горизонт.
            value_json (dict): Данные статистики.
            error_message (str | None): Сообщение об ошибке (если была).

        Возвращает:
            NovaStatCache: Обновленный объект кэша.
        """
        cache = await self.get_cache(channel_identifier, horizon)

        current_time = int(time.time())

        if cache:
            # Обновить существующий
            stmt = (
                update(NovaStatCache)
                .where(NovaStatCache.id == cache.id)
                .values(
                    value_json=value_json,
                    updated_at=current_time,
                    refresh_in_progress=False,
                    error_message=error_message,
                )
            )
            await self.execute(stmt)
            cache.value_json = value_json
            cache.updated_at = current_time
            cache.refresh_in_progress = False
            cache.error_message = error_message
            return cache
        else:
            # Создать новый
            new_cache = NovaStatCache(
                channel_identifier=channel_identifier,
                horizon=horizon,
                value_json=value_json,
                updated_at=current_time,
                refresh_in_progress=False,
                error_message=error_message,
            )
            await self.add(new_cache)
            return new_cache

    async def mark_refresh_in_progress(
        self, channel_identifier: str, horizon: int, in_progress: bool
    ) -> None:
        """
        Устанавливает флаг процесса обновления кэша.

        Аргументы:
            channel_identifier (str): Идентификатор канала.
            horizon (int): Горизонт.
            in_progress (bool): Статус выполнения.
        """
        cache = await self.get_cache(channel_identifier, horizon)

        if cache:
            stmt = (
                update(NovaStatCache)
                .where(NovaStatCache.id == cache.id)
                .values(refresh_in_progress=in_progress)
            )
            await self.execute(stmt)
        elif in_progress:
            # Создать запись с флагом in_progress
            new_cache = NovaStatCache(
                channel_identifier=channel_identifier,
                horizon=horizon,
                value_json={},
                updated_at=0,  # Еще не обновлено
                refresh_in_progress=True,
                error_message=None,
            )
            await self.add(new_cache)

    async def clear_stale_refresh_flags(self, max_age_seconds: int = 600) -> None:
        """
        Сбрасывает зависшие флаги refresh_in_progress (старше max_age_seconds).

        Аргументы:
            max_age_seconds (int): Максимальное время висения флага (по умолч. 10 мин).
        """
        current_time = int(time.time())
        cutoff = current_time - max_age_seconds

        stmt = (
            update(NovaStatCache)
            .where(
                NovaStatCache.refresh_in_progress,
                NovaStatCache.updated_at < cutoff,
            )
            .values(
                refresh_in_progress=False,
                error_message="Timeout: refresh took too long",
            )
        )
        await self.execute(stmt)
