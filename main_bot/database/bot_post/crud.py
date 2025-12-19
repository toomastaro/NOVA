"""
Модуль операций базы данных для постов бота.
"""

import logging
import time
from datetime import datetime
from typing import List

from sqlalchemy import and_, delete, func, insert, or_, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.bot_post.model import BotPost
from main_bot.database.db_types import Status

logger = logging.getLogger(__name__)


class BotPostCrud(DatabaseMixin):
    """
    Класс для управления постами бота (BotPost).
    """

    async def add_bot_post(self, return_obj: bool = False, **kwargs) -> BotPost | None:
        """
        Создает новый пост бота.

        Аргументы:
            return_obj (bool): Если True, возвращает созданный объект.
            **kwargs: Поля модели BotPost.

        Возвращает:
            BotPost | None: Объект поста или None (если return_obj=False или create failed).
        """
        stmt = insert(BotPost).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(BotPost)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def get_bot_post(self, post_id: int) -> BotPost:
        """
        Получает пост по ID.
        """
        return await self.fetchrow(select(BotPost).where(BotPost.id == post_id))

    async def update_bot_post(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> BotPost | None:
        """
        Обновляет пост.

        Аргументы:
            post_id (int): ID поста.
            return_obj (bool): Вернуть ли обновленный объект.
            **kwargs: Поля для обновления.
        """
        stmt = update(BotPost).where(BotPost.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(BotPost)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_bot_post(self, post_id: int):
        """
        Удаляет пост по ID.
        """
        return await self.execute(delete(BotPost).where(BotPost.id == post_id))

    async def get_bot_posts(self, chat_id: int, current_day: datetime = None):
        """
        Получает список постов для конкретного чата (админа).

        Аргументы:
            chat_id (int): ID чата/админа.
            current_day (datetime, опционально): Фильтр по дате.
        """
        stmt = select(BotPost).where(BotPost.chat_ids.contains([chat_id]))

        # Убрали фильтр по статусу - показываем все посты (PENDING, FINISH, DELETED, ERROR)
        # чтобы видеть полную историю действий

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
                or_(
                    and_(
                        BotPost.send_time.isnot(None),
                        BotPost.send_time >= start_day,
                        BotPost.send_time < end_day,
                    ),
                    and_(
                        BotPost.send_time.is_(None),
                        BotPost.start_timestamp >= start_day,
                        BotPost.start_timestamp < end_day,
                    ),
                )
            )

        return await self.fetch(stmt)

    async def get_bot_posts_for_clear_messages(self):
        """
        Получает посты, сообщения которых нужно удалить (истек delete_time).
        """
        return await self.fetch(
            select(BotPost).where(
                BotPost.status == Status.FINISH,
                BotPost.message_ids.isnot(None),
                BotPost.delete_time.isnot(None),
            )
        )

    async def clear_empty_bot_posts(self):
        """
        Удаляет пустые посты (без получателей) старше недели.
        """
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(BotPost).where(
                func.cardinality(BotPost.bot_ids) == 0,
                BotPost.created_timestamp < week_ago,
            )
        )

    async def get_bot_post_for_send(self):
        """
        Получает посты, готовые к отправке сейчас.
        """
        current_time = int(time.time())

        return await self.fetch(
            select(BotPost).where(
                or_(
                    and_(BotPost.send_time.is_(None), BotPost.status == Status.READY),
                    and_(
                        BotPost.send_time < current_time,
                        BotPost.status == Status.PENDING,
                    ),
                )
            )
        )

    async def clear_bot_posts(self, post_ids: List[int]):
        """
        Удаляет список постов по ID.
        """
        await self.execute(delete(BotPost).where(BotPost.id.in_(post_ids)))
    async def count_user_bot_posts(self, user_id: int) -> int:
        """
        Подсчитывает количество рассылок пользователя через ботов.
        """
        stmt = select(func.count(BotPost.id)).where(BotPost.admin_id == user_id)
        result = await self.fetchrow(stmt)
        return result if result is not None else 0
