import logging
from typing import List

from main_bot.database import DatabaseMixin
from main_bot.database.user.model import User
from sqlalchemy import func, insert, select, update

logger = logging.getLogger(__name__)


class UserCrud(DatabaseMixin):
    async def get_users(self) -> List[User]:
        """
        Получает список всех пользователей.
        :return: Список объектов User.
        """
        return await self.fetch(select(User))

    async def get_user(self, user_id: int) -> User | None:
        """
        Получает пользователя по ID.
        :param user_id: Telegram ID пользователя.
        :return: Объект User или None.
        """
        return await self.fetchrow(select(User).where(User.id == user_id))

    async def get_count_user_referral(self, user_id: int) -> int:
        """
        Считает количество рефералов пользователя.
        :param user_id: ID пользователя.
        :return: Количество рефералов.
        """
        res = await self.fetchrow(
            select(func.count(User.id)).where(User.referral_id == user_id)
        )
        return res if res else 0

    async def add_user(self, **kwargs) -> None:
        """
        Добавляет нового пользователя.
        :param kwargs: Поля модели User.
        """
        await self.execute(insert(User).values(**kwargs))

    async def update_user(
        self, user_id: int, return_obj: bool = False, **kwargs
    ) -> User | None:
        """
        Обновляет данные пользователя.
        :param user_id: ID пользователя.
        :param return_obj: Возвращать ли обновленный объект.
        :param kwargs: Поля для обновления.
        :return: Обновленный User или None.
        """
        stmt = update(User).where(User.id == user_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(User)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})
