"""
Модуль операций базы данных для опубликованных постов.
"""

import logging
import time
from typing import List

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.published_post.model import PublishedPost

logger = logging.getLogger(__name__)


class PublishedPostCrud(DatabaseMixin):
    """
    Класс для управления историей опубликованных постов.
    """

    async def add_many_published_post(self, posts: List[dict]) -> None:
        """
        Массовое добавление опубликованных постов.

        Аргументы:
            posts (List[dict]): Список словарей с данными постов.
        """
        await self.execute(insert(PublishedPost).values(posts))

    async def delete_published_posts(self, row_ids: List[int]) -> None:
        """
        Полное удаление записей по ID.

        Аргументы:
            row_ids (List[int]): ID записей.
        """
        logger.info(f"Удаление published posts: {row_ids}")
        await self.execute(delete(PublishedPost).where(PublishedPost.id.in_(row_ids)))

    async def soft_delete_published_posts(self, row_ids: List[int]) -> None:
        """
        Мягкое удаление (помечает как deleted).

        Аргументы:
            row_ids (List[int]): ID записей.
        """
        logger.info(f"Soft delete published posts: {row_ids}")
        await self.execute(
            update(PublishedPost)
            .where(PublishedPost.id.in_(row_ids))
            .values(status="deleted", deleted_at=int(time.time()))
        )

    async def get_posts_for_unpin(self) -> List[PublishedPost]:
        """
        Получает посты, которые нужно открепить (время unpin_time наступило).

        Возвращает:
            List[PublishedPost]: Список постов.
        """
        current_time = int(time.time())

        return await self.fetch(
            select(PublishedPost).where(
                PublishedPost.unpin_time < current_time,
                PublishedPost.status == "active",
            )
        )

    async def get_posts_for_delete(self) -> List[PublishedPost]:
        """
        Получает посты, которые нужно удалить из канала (время delete_time наступило).

        Возвращает:
            List[PublishedPost]: Список постов.
        """
        current_time = int(time.time())

        return await self.fetch(
            select(PublishedPost).where(
                PublishedPost.delete_time < current_time,
                PublishedPost.status == "active",
            )
        )

    async def get_published_post(
        self, chat_id: int, message_id: int
    ) -> PublishedPost | None:
        """
        Получает опубликованный пост по чату и ID сообщения.

        Аргументы:
            chat_id (int): ID чата.
            message_id (int): ID сообщения.

        Возвращает:
            PublishedPost | None: Пост или None.
        """
        return await self.fetchrow(
            select(PublishedPost).where(
                PublishedPost.chat_id == chat_id, PublishedPost.message_id == message_id
            )
        )

    async def get_published_post_by_id(self, post_id: int) -> PublishedPost | None:
        """
        Получает опубликованный пост по внутреннему ID.

        Аргументы:
            post_id (int): ID записи (PK).

        Возвращает:
            PublishedPost | None: Пост или None.
        """
        return await self.fetchrow(
            select(PublishedPost).where(PublishedPost.id == post_id)
        )

    async def update_published_post(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> PublishedPost | None:
        """
        Обновляет запись об опубликованном посте.

        Аргументы:
            post_id (int): ID записи.
            return_obj (bool): Возвращать обновленный объект.
            **kwargs: Поля для обновления.

        Возвращает:
            PublishedPost | None: Обновленный пост.
        """
        stmt = update(PublishedPost).where(PublishedPost.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(PublishedPost)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def get_published_posts_by_post_id(self, post_id: int) -> List[PublishedPost]:
        """
        Получает все публикации конкретного родительского поста.

        Аргументы:
            post_id (int): ID родительского поста (Post.id).

        Возвращает:
            List[PublishedPost]: Список публикаций.
        """
        return await self.fetch(
            select(PublishedPost).where(PublishedPost.post_id == post_id)
        )

    async def update_published_posts_by_post_id(self, post_id: int, **kwargs) -> None:
        """
        Обновляет все публикации конкретного родительского поста.

        Аргументы:
            post_id (int): ID родительского поста (Post.id).
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(PublishedPost)
            .where(PublishedPost.post_id == post_id)
            .values(**kwargs)
        )

    async def update_published_posts_batch(self, updates: List[dict]) -> None:
        """
        Массовое обновление опубликованных постов (bulk update).

        Аргументы:
            updates (List[dict]): Список словарей, каждый из которых содержит 'id'
                                  и поля для обновления.
        """
        if not updates:
            return

        stmts = [
            update(PublishedPost)
            .where(PublishedPost.id == u["id"])
            .values(**{k: v for k, v in u.items() if k != "id"})
            for u in updates
        ]
        await self.execute_many(stmts)
    async def count_user_published(self, user_id: int) -> int:
        """
        Подсчитывает количество опубликованных постов пользователя.
        """
        from sqlalchemy import func
        stmt = select(func.count(PublishedPost.id)).where(PublishedPost.admin_id == user_id)
        result = await self.fetchrow(stmt)
        return result if result is not None else 0
