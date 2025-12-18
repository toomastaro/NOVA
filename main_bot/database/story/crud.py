"""
Модуль операций базы данных для сторис.
"""

import logging
import time
from datetime import datetime
from typing import List

from sqlalchemy import delete, func, insert, or_, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.db_types import Status
from main_bot.database.story.model import Story

logger = logging.getLogger(__name__)


class StoryCrud(DatabaseMixin):
    """
    Класс для управления сторис (планирование, статус, очистка).
    """

    async def add_story(self, return_obj: bool = False, **kwargs) -> Story | None:
        """
        Добавляет новую сторис.

        Аргументы:
            return_obj (bool): Возвращать объект.
            **kwargs: Поля модели Story.

        Возвращает:
            Story | None: Объект сторис или None.
        """
        stmt = insert(Story).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Story)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def update_story(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> Story | None:
        """
        Обновляет данные сторис.

        Аргументы:
            post_id (int): ID записи.
            return_obj (bool): Возвращать обновленный объект.
            **kwargs: Поля для обновления.

        Возвращает:
            Story | None: Обновленный объект сторис.
        """
        stmt = update(Story).where(Story.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Story)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_story(self, post_id: int) -> None:
        """
        Удаляет сторис по ID.
        """
        await self.execute(delete(Story).where(Story.id == post_id))

    async def get_story(self, post_id: int) -> Story | None:
        """
        Получает сторис по ID.
        """
        return await self.fetchrow(select(Story).where(Story.id == post_id))

    async def get_stories(
        self, chat_id: int, current_day: datetime = None, only_pending: bool = False
    ) -> List[Story]:
        """
        Получает запланированные сторис для канала.

        Аргументы:
            chat_id (int): ID канала/чата.
            current_day (datetime): День для фильтрации (по умолчанию None).
            only_pending (bool): Фильтровать только ожидающие публикации (будущие) истории.

        Возвращает:
            List[Story]: Список сторис.
        """
        stmt = select(Story).where(
            Story.chat_ids.contains([chat_id]), Story.send_time.isnot(None)
        )

        if only_pending:
            current_time = int(time.time())
            stmt = stmt.where(
                Story.status == Status.PENDING,
                Story.send_time > current_time,
            )

        if current_day:
            start_day = int(
                time.mktime(
                    current_day.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ).timetuple()
                )
            )
            end_day = start_day + 86400
            stmt = stmt.where(
                Story.send_time >= start_day,
                Story.send_time < end_day,
            )

        # Сортировка по времени отправки (ближайшие первыми)
        stmt = stmt.order_by(Story.send_time.asc())

        return await self.fetch(stmt)

    async def get_story_for_send(self) -> List[Story]:
        """
        Получает сторис, готовые к отправке.

        Возвращает:
            List[Story]: Список сторис со статусом PENDING и наступившим временем отправки.
        """
        current_time = int(time.time())

        return await self.fetch(
            select(Story).where(
                func.cardinality(Story.chat_ids) > 0,
                or_(Story.send_time.is_(None), Story.send_time < current_time),
                Story.status == Status.PENDING,
            )
        )

    async def clear_story(self, post_ids: List[int]) -> None:
        """
        Массовое удаление сторис по ID.
        """
        await self.execute(delete(Story).where(Story.id.in_(post_ids)))

    async def clear_empty_stories(self) -> None:
        """
        Очищает старые сторис (старше недели) без адресатов.
        """
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(Story).where(
                func.cardinality(Story.chat_ids) == 0,
                Story.created_timestamp < week_ago,
            )
        )
