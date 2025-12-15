import logging
import time
from datetime import datetime
from typing import List

from main_bot.database import DatabaseMixin
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from sqlalchemy import delete, func, insert, select, update

logger = logging.getLogger(__name__)


class PostCrud(DatabaseMixin):
    async def add_post(self, return_obj: bool = False, **kwargs) -> Post | None:
        """
        Добавляет новый пост в базу данных (черновик или запланированный).
        :param return_obj: Если True, возвращает созданный объект Post.
        :param kwargs: Поля модели Post.
        :return: Объект Post или None.
        """
        stmt = insert(Post).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def get_post(self, post_id: int) -> Post | None:
        """
        Получает пост по ID.
        :param post_id: ID поста.
        :return: Объект Post.
        """
        return await self.fetchrow(select(Post).where(Post.id == post_id))

    async def update_post(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> Post | None:
        """
        Обновляет существующий пост.
        :param post_id: ID поста.
        :param return_obj: Возвращать ли обновленный объект.
        :param kwargs: Поля для обновления.
        :return: Обновленный Post или None.
        """
        stmt = update(Post).where(Post.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_post(self, post_id: int) -> None:
        """
        Удаляет пост по ID.
        :param post_id: ID поста.
        """
        logger.info(f"Deleting post {post_id}")
        return await self.execute(delete(Post).where(Post.id == post_id))

    async def get_posts(
        self, chat_id: int, current_day: datetime = None, only_scheduled: bool = False
    ) -> List[Post | PublishedPost]:
        """
        Получает список постов (запланированных и опубликованных) для конкретного чата.
        :param chat_id: ID канала/чата.
        :param current_day: День для фильтрации (по умолчанию None - все).
        :param only_scheduled: Если True, возвращает только запланированные (Post).
        :return: Список постов, отсортированный по времени отправки.
        """
        # Запланированные посты (Post)
        stmt_posts = (
            select(Post)
            .where(Post.chat_ids.contains([chat_id]), Post.send_time.isnot(None))
            .order_by(Post.send_time)
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

            stmt_posts = stmt_posts.where(
                Post.send_time >= start_day,
                Post.send_time < end_day,
            )

        posts = await self.fetch(stmt_posts)

        published = []
        if not only_scheduled:
            # Опубликованные посты (PublishedPost)
            stmt_published = (
                select(PublishedPost)
                .where(PublishedPost.chat_id == chat_id)
                .order_by(PublishedPost.created_timestamp)
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

                stmt_published = stmt_published.where(
                    PublishedPost.created_timestamp >= start_day,
                    PublishedPost.created_timestamp < end_day,
                )
            published = await self.fetch(stmt_published)

        # Объединение и сортировка
        all_posts = []
        for p in posts:
            p.status = "scheduled"  # Временное поле для UI
            all_posts.append(p)

        for p in published:
            # Маппинг created_timestamp в send_time для единой сортировки
            p.send_time = p.created_timestamp
            all_posts.append(p)

        # Сортировка: Новые (будущие) сверху, старые снизу (DESC)
        all_posts.sort(key=lambda x: x.send_time if x.send_time else 0, reverse=True)

        return all_posts

    async def clear_empty_posts(self) -> None:
        """
        Очищает посты без чатов старше 2 недель.
        """
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(Post).where(
                func.cardinality(Post.chat_ids) == 0, Post.created_timestamp < week_ago
            )
        )

    async def get_post_for_send(self) -> List[Post]:
        """
        Получает посты, готовые к отправке (время отправки наступило).
        :return: Список постов для отправки.
        """
        current_time = int(time.time())

        return await self.fetch(
            select(Post).where(
                func.cardinality(Post.chat_ids) > 0,
                Post.send_time.isnot(None),
                Post.send_time < current_time,
            )
        )

    async def clear_posts(self, post_ids: List[int]) -> None:
        """
        Удаляет список постов по их ID.
        :param post_ids: Список ID постов.
        """
        logger.info(f"Clearing posts: {post_ids}")
        await self.execute(delete(Post).where(Post.id.in_(post_ids)))
