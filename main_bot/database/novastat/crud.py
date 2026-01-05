"""
Модуль операций базы данных для NovaStat.
"""

import logging
import time
from datetime import datetime, timezone, timedelta

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

    async def check_and_update_limit(
        self, user_id: int, max_limit: int, increment: bool = True
    ) -> tuple[bool, int, int]:
        """
        Проверяет и обновляет суточный лимит пользователя.

        Аргументы:
            user_id (int): ID пользователя.
            max_limit (int): Максимальный суточный лимит.
            increment (bool): Увеличивать ли счетчик (False для проверки или внутренних каналов).

        Возвращает:
            tuple[bool, int, int]: (Лимит не исчерпан, текущее кол-во, время до сброса)
        """
        settings = await self.get_novastat_settings(user_id)
        now_ts = int(time.time())

        # Конец текущих суток (сброс)
        now_dt = datetime.fromtimestamp(now_ts, tz=timezone.utc)
        reset_dt = datetime(
            now_dt.year, now_dt.month, now_dt.day, tzinfo=timezone.utc
        ) + timedelta(days=1)
        reset_ts = int(reset_dt.timestamp())

        # Если время последнего сброса меньше начала текущих суток - обнуляем
        start_of_day_ts = reset_ts - 86400
        if settings.last_check_reset < start_of_day_ts:
            # Сброс счетчика
            current_count = 0
            await self.update_novastat_settings(
                user_id, daily_check_count=current_count, last_check_reset=now_ts
            )
        else:
            current_count = settings.daily_check_count

        # Если не нужно увеличивать счетчик, просто возвращаем статус
        if not increment:
            # Если лимит уже исчерпан, но мы проверяем "свои" каналы - разрешаем?
            # ЛОГИКА: "свои" каналы безлимитны. Значит всегда True?
            # Или мы хотим запретить даже свои, если лимит на внешние исчерпан?
            # User request: "счетчик актуален только для внешних, если проверка пошал через свои, там ограничений нет"
            # Значит, если increment=False (свои каналы), мы должны вернуть True, даже если счетчик полон.
            return True, current_count, reset_ts - now_ts

        # Проверка лимита (для внешних)
        if current_count >= max_limit:
            return False, current_count, reset_ts - now_ts

        # Инкремент
        new_count = current_count + 1
        await self.update_novastat_settings(
            user_id, daily_check_count=new_count, last_check_reset=now_ts
        )
        return True, new_count, reset_ts - now_ts

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
        # Жадная загрузка каналов (Eager load)
        # Примечание: простой select может не загружать отношения без опций,
        # лучше запросить каналы явно.
        return await self.fetchrow(
            select(Collection).where(Collection.id == collection_id)
        )

    async def get_collection_channels(
        self, collection_id: int
    ) -> list[CollectionChannel]:
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
        # Вручную удаляем каналы, так как используем Core delete, который обходит ORM cascade
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
