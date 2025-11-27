from typing import Literal

from sqlalchemy import insert, select, desc, update, delete, or_

from main_bot.database import DatabaseMixin
from main_bot.database.channel.model import Channel


class ChannelCrud(DatabaseMixin):
    async def get_subscribe_channels(self, user_id: int):
        return await self.fetch(
            select(Channel).where(
                Channel.admin_id == user_id,
                Channel.subscribe.is_not(None)
            )
        )

    async def get_user_channels(
            self,
            user_id: int,
            limit: int = None,
            sort_by: Literal['subscribe'] = None,
            from_array: list = None
    ):
        stmt = select(Channel).where(Channel.admin_id == user_id)

        if sort_by:
            stmt = stmt.order_by(desc(Channel.subscribe))

        if limit:
            stmt = stmt.limit(limit)
        if from_array:
            stmt = stmt.where(Channel.chat_id.in_(from_array))

        return await self.fetch(stmt)

    async def get_channel_by_row_id(self, row_id: int) -> Channel:
        return await self.fetchrow(
            select(Channel).where(
                Channel.id == row_id
            )
        )

    async def get_channel_admin_row(self, chat_id: int, user_id: int) -> Channel:
        return await self.fetchrow(
            select(Channel).where(
                Channel.chat_id == chat_id,
                Channel.admin_id == user_id
            )
        )

    async def get_channel_by_chat_id(self, chat_id: int) -> Channel:
        return await self.fetchrow(
            select(Channel).where(
                Channel.chat_id == chat_id
            ).limit(1)
        )

    async def update_channel_by_chat_id(self, chat_id: int, **kwargs):
        await self.execute(
            update(Channel).where(
                Channel.chat_id == chat_id
            ).values(**kwargs)
        )

    async def add_channel(self, **kwargs):
        await self.execute(
            insert(Channel).values(**kwargs)
        )

    async def delete_channel(self, chat_id: int, user_id: int = None):
        stmt = delete(Channel).where(Channel.chat_id == chat_id)
        if user_id:
            stmt = stmt.where(Channel.admin_id == user_id)

        await self.execute(stmt)

    async def get_active_channels(self):
        stmt = (
            select(Channel)
            .where(
                Channel.subscribe.is_not(None),
            )
            .order_by(Channel.id.asc())
        )
        return await self.fetch(stmt)
