"""
Модуль операций базы данных для пользователя.
"""

import logging
from typing import List

from sqlalchemy import func, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.user.model import User

logger = logging.getLogger(__name__)


class UserCrud(DatabaseMixin):
    """
    Класс для управления пользователями.
    """

    async def get_users(self) -> List[User]:
        """
        Получает список всех пользователей.

        Возвращает:
            List[User]: Список объектов User.
        """
        return await self.fetch(select(User))

    async def get_user(self, user_id: int) -> User | None:
        """
        Получает пользователя по ID.

        Аргументы:
            user_id (int): Telegram ID пользователя.

        Возвращает:
            User | None: Объект User или None.
        """
        return await self.fetchrow(select(User).where(User.id == user_id))

    async def get_count_user_referral(self, user_id: int) -> int:
        """
        Считает количество рефералов пользователя.

        Аргументы:
            user_id (int): ID пользователя.

        Возвращает:
            int: Количество рефералов.
        """
        res = await self.fetchrow(
            select(func.count(User.id)).where(User.referral_id == user_id)
        )
        return res if res else 0

    async def add_user(self, **kwargs) -> None:
        """
        Добавляет нового пользователя.

        Аргументы:
            **kwargs: Поля модели User.
        """
        await self.execute(insert(User).values(**kwargs))

    async def update_user(
        self, user_id: int, return_obj: bool = False, **kwargs
    ) -> User | None:
        """
        Обновляет данные пользователя.

        Аргументы:
            user_id (int): ID пользователя.
            return_obj (bool): Возвращать ли обновленный объект.
            **kwargs: Поля для обновления.

        Возвращает:
            User | None: Обновленный User или None.
        """
        stmt = update(User).where(User.id == user_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(User)
        else:
            operation = self.execute
            stmt = stmt.execution_options(synchronize_session=None)

        return await operation(stmt, **{"commit": True} if return_obj else {})

    async def increment_balance(self, user_id: int, amount: int) -> None:
        """
        Атомарно увеличивает баланс пользователя.
        Предотвращает race conditions.
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(balance=User.balance + amount)
        )
        await self.execute(stmt, commit=True)

    async def add_referral_reward(self, user_id: int, amount: int) -> None:
        """
        Атомарно начисляет реферальное вознаграждение (баланс + статистика).
        """
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values(
                balance=User.balance + amount,
                referral_earned=User.referral_earned + amount
            )
        )
        await self.execute(stmt, commit=True)

    async def toggle_signature_active(
        self, user_id: int, setting_type: str
    ) -> User | None:
        """
        Атомарно переключает состояние активности подписи (bool) и возвращает объект пользователя.
        Используется для оптимизации производительности (1 запрос вместо 3-х).

        Аргументы:
            user_id (int): ID пользователя.
            setting_type (str): Тип настройки ('cpm', 'exchange', 'referral').

        Возвращает:
            User | None: Обновленный объект пользователя.
        """
        field_map = {
            "cpm": User.cpm_signature_active,
            "exchange": User.exchange_signature_active,
            "referral": User.referral_signature_active,
        }

        field = field_map.get(setting_type)
        if field is None:
            return None

        # Атомарный UPDATE с использованием SQL NOT и RETURNING
        stmt = (
            update(User)
            .where(User.id == user_id)
            .values({field: ~field})
            .returning(User)
        )

        return await self.fetchrow(stmt, commit=True)
