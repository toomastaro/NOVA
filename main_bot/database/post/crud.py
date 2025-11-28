import time
from datetime import datetime

from sqlalchemy import delete, func, insert, or_, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.post.model import Post
from main_bot.database.types.post_status import PostStatus


class PostCrud(DatabaseMixin):
    async def add_post(self, return_obj: bool = False, **kwargs) -> Post | None:
        stmt = insert(Post).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def get_post(self, post_id: int) -> Post:
        return await self.fetchrow(select(Post).where(Post.id == post_id))

    async def update_post(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> Post | None:
        stmt = update(Post).where(Post.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_post(self, post_id: int):
        return await self.execute(delete(Post).where(Post.id == post_id))

    async def get_posts(self, chat_id: int, current_day: datetime = None):
        # Показываем посты с этим каналом в списке каналов
        # включая отложенные и уже опубликованные
        stmt = select(Post).where(
            Post.chat_ids.contains([chat_id])
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

            # Ищем посты, которые запланированы на этот день
            # или уже опубликованы в этот день
            stmt = stmt.where(
                or_(
                    # Отложенные посты
                    Post.send_time.between(start_day, end_day),
                    # Опубликованные посты
                    Post.posted_timestamp.between(start_day, end_day)
                )
            )

        # Показываем все, кроме удаленных
        stmt = stmt.where(Post.status != PostStatus.DELETED)

        return await self.fetch(stmt.order_by(Post.send_time.desc().nulls_last(), Post.created_timestamp.desc()))

    async def clear_empty_posts(self):
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(Post).where(
                func.cardinality(Post.chat_ids) == 0, Post.created_timestamp < week_ago
            )
        )

    async def get_post_for_send(self):
        current_time = int(time.time())

        return await self.fetch(
            select(Post).where(
                func.cardinality(Post.chat_ids) > 0,
                or_(Post.send_time.is_(None), Post.send_time < current_time),
                Post.status == PostStatus.PENDING  # Только ожидающие отправки
            )
        )

    async def clear_posts(self, post_ids: list[int]):
        await self.execute(delete(Post).where(Post.id.in_(post_ids)))

    async def get_by_id(self, post_id: int) -> Post | None:
        """Получить пост по ID"""
        return await self.fetchrow(select(Post).where(Post.id == post_id))

    async def update(self, post_id: int, **kwargs) -> bool:
        """Обновить пост"""
        result = await self.execute(
            update(Post).where(Post.id == post_id).values(**kwargs)
        )
        return result.rowcount > 0

    async def get_posts_older_than(self, timestamp: float) -> list[Post]:
        """Получить посты старше указанной временной метки"""
        return await self.fetch(
            select(Post).where(Post.created_timestamp < timestamp)
        )

    async def update_post_status(self, post_id: int, status: PostStatus, posted_timestamp: int = None) -> bool:
        """Обновить статус поста"""
        update_data = {'status': status}
        if posted_timestamp:
            update_data['posted_timestamp'] = posted_timestamp

        result = await self.execute(
            update(Post).where(Post.id == post_id).values(**update_data)
        )
        return result.rowcount > 0

    async def get_posts_by_status(self, status: PostStatus, admin_id: int = None) -> list[Post]:
        """Получить посты по статусу"""
        stmt = select(Post).where(Post.status == status)
        if admin_id:
            stmt = stmt.where(Post.admin_id == admin_id)
        return await self.fetch(stmt)

    async def get_posts_for_calendar(self, admin_id: int, current_day: datetime = None) -> list[Post]:
        """Получить посты для календаря (включая отправленные)"""
        # Ограничиваем 90 днями
        cutoff_time = time.time() - (90 * 24 * 60 * 60)

        stmt = select(Post).where(
            Post.admin_id == admin_id,
            Post.created_timestamp >= cutoff_time,
            # Показываем все, кроме удаленных старше 7 дней
            or_(
                Post.status != PostStatus.DELETED,
                Post.posted_timestamp >= (time.time() - (7 * 24 * 60 * 60))
            )
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

            # Для конкретного дня ищем по send_time или posted_timestamp
            stmt = stmt.where(
                or_(
                    # Отложенные посты
                    (Post.send_time.between(start_day, end_day)),
                    # Отправленные посты
                    (Post.posted_timestamp.between(start_day, end_day))
                )
            )

        return await self.fetch(stmt.order_by(Post.created_timestamp.desc()))

    async def delete_old_posts(self, cutoff_timestamp: float) -> int:
        """Удалить посты старше 90 дней"""
        result = await self.execute(
            delete(Post).where(Post.created_timestamp < cutoff_timestamp)
        )
        return result.rowcount
