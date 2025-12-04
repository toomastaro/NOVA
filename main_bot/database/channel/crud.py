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

    async def get_user_channels_without_folders(self, user_id: int):
        from main_bot.database.user_folder.model import UserFolder
        from main_bot.database.types import FolderType

        # Get all chat_ids from user folders
        stmt_folders = select(UserFolder.content).where(
            UserFolder.user_id == user_id,
            UserFolder.type == FolderType.CHANNEL
        )
        folders_content = await self.fetch(stmt_folders)
        
        # Flatten the list of lists and convert to int
        excluded_chat_ids = []
        for content in folders_content:
            if content:
                excluded_chat_ids.extend([int(c) for c in content])
        
        # Get channels not in excluded_chat_ids
        stmt = select(Channel).where(Channel.admin_id == user_id)
        
        if excluded_chat_ids:
            stmt = stmt.where(Channel.chat_id.notin_(excluded_chat_ids))
            
        return await self.fetch(stmt)
    
    async def update_last_client(self, channel_id: int, client_id: int):
        """
        Обновить last_client_id для канала (для round-robin распределения).
        
        Args:
            channel_id: ID канала (row id, не chat_id)
            client_id: ID клиента
        """
        await self.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(last_client_id=client_id)
        )

    async def get_all_channels(self):
        """Получить все каналы (для админ-панели)"""
        channels = await self.fetch(
            select(Channel).order_by(Channel.id.desc())
        )
        
        # Filter duplicates by chat_id, keeping the newest (first in list)
        seen = set()
        unique_channels = []
        for ch in channels:
            if ch.chat_id not in seen:
                unique_channels.append(ch)
                seen.add(ch.chat_id)
                
        return unique_channels

    async def get_channel_by_id(self, channel_id: int):
        """Получить канал по ID (row_id)"""
        return await self.get_channel_by_row_id(channel_id)

