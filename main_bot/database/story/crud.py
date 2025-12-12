import time
from datetime import datetime
from typing import List

from sqlalchemy import insert, update, delete, select, or_, func

from main_bot.database import DatabaseMixin
from main_bot.database.story.model import Story
from main_bot.database.types import Status



class StoryCrud(DatabaseMixin):
    async def add_story(self, return_obj: bool = False, **kwargs) -> Story | None:
        stmt = insert(Story).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Story)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def update_story(self, post_id: int, return_obj: bool = False, **kwargs) -> Story | None:
        stmt = update(Story).where(Story.id == post_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(Story)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})

    async def delete_story(self, post_id: int):
        return await self.execute(
            delete(Story).where(Story.id == post_id)
        )

    async def get_story(self, post_id: int) -> Story:
        return await self.fetchrow(
            select(Story).where(Story.id == post_id)
        )

    async def get_stories(self, chat_id: int, current_day: datetime = None):
        stmt = select(Story).where(
            Story.chat_ids.contains([chat_id]),
            Story.send_time.isnot(None)
        )

        if current_day:
            start_day = int(time.mktime(current_day.replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
            end_day = start_day + 86400
            stmt = stmt.where(
                Story.send_time >= start_day,
                Story.send_time < end_day,
            )

        return await self.fetch(stmt)

    async def get_story_for_send(self):
        current_time = int(time.time())

        return await self.fetch(
            select(Story).where(
                func.cardinality(Story.chat_ids) > 0,
                or_(
                    Story.send_time.is_(None),
                    Story.send_time < current_time
                ),
                Story.status == Status.PENDING
            )
        )

    async def clear_story(self, post_ids: List[int]):
        await self.execute(
            delete(Story).where(
                Story.id.in_(post_ids)
            )
        )

    async def clear_empty_stories(self):
        week_ago = int(time.time()) - 7 * 24 * 60 * 60

        await self.execute(
            delete(Story).where(
                func.cardinality(Story.chat_ids) == 0,
                Story.created_timestamp < week_ago
            )
        )
