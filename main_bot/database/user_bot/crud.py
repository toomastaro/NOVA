"""
Модуль операций базы данных для управления юзерботами.
"""

import logging
from typing import List

from sqlalchemy import delete, desc, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.user_bot.model import UserBot

logger = logging.getLogger(__name__)


class UserBotCrud(DatabaseMixin):
    """
    Класс для управления юзерботами.
    """

    async def add_bot(self, **kwargs) -> None:
        """
        Добавляет нового юзербота.

        Аргументы:
            **kwargs: Поля модели UserBot.
        """
        await self.execute(insert(UserBot).values(**kwargs))

    async def get_active_bots(self) -> List[UserBot]:
        """
        Получает список активных ботов с подпиской.

        Возвращает:
            List[UserBot]: Список активных ботов.
        """
        stmt = (
            select(UserBot)
            .where(UserBot.subscribe.is_not(None))
            .order_by(UserBot.subscribe.asc())
        )
        return await self.fetch(stmt)

    async def get_user_bots(
        self, user_id: int, limit: int = None, sort_by: bool = None
    ) -> List[UserBot]:
        """
        Получает ботов конкретного пользователя.

        Аргументы:
            user_id (int): ID пользователя.
            limit (int | None): Лимит количества.
            sort_by (bool | None): Сортировка по подписке (desc).

        Возвращает:
            List[UserBot]: Список ботов.
        """
        stmt = select(UserBot).where(UserBot.admin_id == user_id)

        if sort_by:
            stmt = stmt.order_by(desc(UserBot.subscribe))
        if limit:
            stmt = stmt.limit(limit)

        return await self.fetch(stmt)

    async def get_bot_by_token(self, token: str) -> UserBot | None:
        """
        Получает бота по токену.
        """
        return await self.fetchrow(select(UserBot).where(UserBot.token == token))

    async def get_bot_by_id(self, row_id: int) -> UserBot | None:
        """
        Получает бота по ID (Primary Key).
        """
        return await self.fetchrow(select(UserBot).where(UserBot.id == row_id))

    async def get_bots_by_ids(self, ids: List[int]) -> List[UserBot]:
        """
        Получает список ботов по списку ID.
        """
        return await self.fetch(select(UserBot).where(UserBot.id.in_(ids)))

    async def delete_bot_by_id(self, row_id: int) -> None:
        """
        Удаляет бота по ID.
        """
        await self.execute(delete(UserBot).where(UserBot.id == row_id))

    async def update_bot_by_id(
        self, row_id: int, return_obj: bool = False, **kwargs
    ) -> UserBot | None:
        """
        Обновляет бота по ID.

        Аргументы:
            row_id (int): ID бота.
            return_obj (bool): Возвращать ли обновленный объект.
            **kwargs: Поля для обновления.

        Возвращает:
            UserBot | None: Обновленный бот или None.
        """
        stmt = update(UserBot).where(UserBot.id == row_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(UserBot)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})
    async def get_all_bots(self) -> List[UserBot]:
        """
        Получает список всех ботов в системе.
        """
        return await self.fetch(select(UserBot).order_by(UserBot.created_timestamp.desc()))
