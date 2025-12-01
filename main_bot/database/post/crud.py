import time
from datetime import datetime
from typing import List

from sqlalchemy import insert, select, update, delete, func, or_

from main_bot.database import DatabaseMixin
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost


class PostCrud(DatabaseMixin):
    async def add_post(self, return_obj: bool = False, **kwargs) -> Post | None:
        stmt = insert(Post).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def get_post(self, post_id: int) -> Post:
        return await self.fetchrow(
            select(Post).where(Post.id == post_id)
        )

    async def update_post(self, post_id: int, return_obj: bool = False, **kwargs) -> Post | None:
        stmt = update(Post).where(Post.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Post)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def delete_post(self, post_id: int):
        return await self.execute(
            delete(Post).where(Post.id == post_id)
        )

    async def get_posts(self, chat_id: int, current_day: datetime = None):
        # Scheduled posts
        stmt_posts = select(Post).where(
            Post.chat_ids.contains([chat_id]),
            Post.send_time.isnot(None)
        )

        # Published posts
        stmt_published = select(PublishedPost).where(
            PublishedPost.chat_id == chat_id
        )

        if current_day:
            start_day = int(time.mktime(current_day.replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
            end_day = start_day + 86400
            
            stmt_posts = stmt_posts.where(
                Post.send_time >= start_day,
                Post.send_time < end_day,
            )
            stmt_published = stmt_published.where(
                PublishedPost.created_timestamp >= start_day,
                PublishedPost.created_timestamp < end_day,
            )

        posts = await self.fetch(stmt_posts)
        published = await self.fetch(stmt_published)

        # Combine and sort
        all_posts = []
        for p in posts:
            p.status = "scheduled"
            all_posts.append(p)
        
        for p in published:
            p.status = "published"
            # Map created_timestamp to send_time for consistent sorting/display if needed
            # But PublishedPost doesn't have send_time in the same way, it has created_timestamp
            # We will use a property or just handle it in the sort key
            p.send_time = p.created_timestamp 
            all_posts.append(p)

        all_posts.sort(key=lambda x: x.send_time)
        
        return all_posts

    async def clear_empty_posts(self):
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(Post).where(
                func.cardinality(Post.chat_ids) == 0,
                Post.created_timestamp < week_ago
            )
        )

    async def get_post_for_send(self):
        current_time = int(time.time())

        return await self.fetch(
            select(Post).where(
                func.cardinality(Post.chat_ids) > 0,
                or_(
                    Post.send_time.is_(None),
                    Post.send_time < current_time
                )
            )
        )

    async def clear_posts(self, post_ids: List[int]):
        await self.execute(
            delete(Post).where(
                Post.id.in_(post_ids)
            )
        )
