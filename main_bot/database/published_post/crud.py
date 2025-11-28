import time

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.published_post.model import PublishedPost


class PublishedPostCrud(DatabaseMixin):
    async def add_many_published_post(self, posts: list[dict]):
        await self.execute(insert(PublishedPost).values(posts))

    async def delete_published_posts(self, row_ids: list[int]):
        await self.execute(delete(PublishedPost).where(PublishedPost.id.in_(row_ids)))

    async def get_posts_for_unpin(self):
        current_time = int(time.time())

        return await self.fetch(
            select(PublishedPost).where(
                PublishedPost.unpin_time < current_time,
            )
        )

    async def get_posts_for_delete(self):
        current_time = int(time.time())

        return await self.fetch(
            select(PublishedPost).where(
                PublishedPost.delete_time < current_time,
            )
        )

    async def get_published_post(self, chat_id: int, message_id: int) -> PublishedPost:
        return await self.fetchrow(
            select(PublishedPost).where(
                PublishedPost.chat_id == chat_id, PublishedPost.message_id == message_id
            )
        )

    async def update_published_post(
        self, post_id: int, return_obj: bool = False, **kwargs
    ) -> PublishedPost | None:
        stmt = update(PublishedPost).where(PublishedPost.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(PublishedPost)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_older_than(self, timestamp: float) -> int:
        """Удалить записи о публикациях старше указанной временной метки"""
        result = await self.execute(
            delete(PublishedPost).where(PublishedPost.created_timestamp < timestamp)
        )
        return result.rowcount

    async def get_by_post_id(self, post_id: int) -> list[PublishedPost]:
        """Получить все публикации поста"""
        return await self.fetch(
            select(PublishedPost).where(PublishedPost.post_id == post_id)
        )
