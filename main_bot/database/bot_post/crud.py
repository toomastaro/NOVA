import time
from datetime import datetime
from typing import List

from sqlalchemy import insert, select, update, delete, func, or_, and_

from main_bot.database import DatabaseMixin
from main_bot.database.bot_post.model import BotPost
from main_bot.database.types import Status


class BotPostCrud(DatabaseMixin):
    async def add_bot_post(self, return_obj: bool = False, **kwargs) -> BotPost | None:
        stmt = insert(BotPost).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(BotPost)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def get_bot_post(self, post_id: int) -> BotPost:
        return await self.fetchrow(
            select(BotPost).where(BotPost.id == post_id)
        )

    async def update_bot_post(self, post_id: int, return_obj: bool = False, **kwargs) -> BotPost | None:
        stmt = update(BotPost).where(BotPost.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(BotPost)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def delete_bot_post(self, post_id: int):
        return await self.execute(
            delete(BotPost).where(BotPost.id == post_id)
        )

    async def get_bot_posts(self, chat_id: int, current_day: datetime = None):
        stmt = select(BotPost).where(
            BotPost.chat_ids.contains([chat_id])
        )
        
        # Убрали фильтр по статусу - показываем все посты (PENDING, FINISH, DELETED, ERROR)
        # чтобы видеть полную историю действий

        if current_day:
            start_day = int(time.mktime(current_day.replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
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
                    )
                )
            )

        return await self.fetch(stmt)

    async def get_bot_posts_for_clear_messages(self):
        return await self.fetch(
            select(BotPost).where(
                BotPost.status == Status.FINISH,
                BotPost.message_ids.isnot(None),
                BotPost.delete_time.isnot(None)
            )
        )

    async def clear_empty_bot_posts(self):
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(BotPost).where(
                func.cardinality(BotPost.bot_ids) == 0,
                BotPost.created_timestamp < week_ago
            )
        )

    async def get_bot_post_for_send(self):
        current_time = int(time.time())

        return await self.fetch(
            select(BotPost).where(
                or_(
                    and_(
                        BotPost.send_time.is_(None),
                        BotPost.status == Status.READY
                    ),
                    and_(
                        BotPost.send_time < current_time,
                        BotPost.status == Status.PENDING
                    )
                )
            )
        )

    async def clear_bot_posts(self, post_ids: List[int]):
        await self.execute(
            delete(BotPost).where(
                BotPost.id.in_(post_ids)
            )
        )
