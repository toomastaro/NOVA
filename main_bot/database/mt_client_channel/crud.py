from typing import Optional
import time

from sqlalchemy import select, update, insert
from main_bot.database import DatabaseMixin
from main_bot.database.mt_client_channel.model import MtClientChannel


class MtClientChannelCrud(DatabaseMixin):
    async def get_or_create_mt_client_channel(self, client_id: int, channel_id: int) -> MtClientChannel:
        stmt = select(MtClientChannel).where(
            MtClientChannel.client_id == client_id,
            MtClientChannel.channel_id == channel_id
        )
        obj = await self.fetchrow(stmt)
        
        if not obj:
            stmt = insert(MtClientChannel).values(
                client_id=client_id,
                channel_id=channel_id
            ).returning(MtClientChannel)
            obj = await self.fetchrow(stmt, commit=True)
            
        return obj

    async def set_membership(self, client_id: int, channel_id: int, **kwargs):
        # Filter allowed keys to avoid errors
        allowed_keys = {
            'is_member', 'is_admin', 'can_post_stories', 
            'last_joined_at', 'last_seen_at', 
            'last_error_code', 'last_error_at',
            'preferred_for_stats', 'preferred_for_stories'
        }
        update_values = {k: v for k, v in kwargs.items() if k in allowed_keys}
        
        if not update_values:
            return

        await self.execute(
            update(MtClientChannel)
            .where(
                MtClientChannel.client_id == client_id,
                MtClientChannel.channel_id == channel_id
            )
            .values(**update_values)
        )

    async def get_preferred_for_stats(self, channel_id: int) -> Optional[MtClientChannel]:
        return await self.fetchrow(
            select(MtClientChannel).where(
                MtClientChannel.channel_id == channel_id,
                MtClientChannel.preferred_for_stats == True
            ).limit(1)
        )

    async def get_preferred_for_stories(self, channel_id: int) -> Optional[MtClientChannel]:
        return await self.fetchrow(
            select(MtClientChannel).where(
                MtClientChannel.channel_id == channel_id,
                MtClientChannel.preferred_for_stories == True
            ).limit(1)
        )
    
    async def get_channels_by_client(self, client_id: int) -> list[MtClientChannel]:
        return await self.fetch(
            select(MtClientChannel).where(MtClientChannel.client_id == client_id)
        )

    async def delete_channels_by_client(self, client_id: int):
        from sqlalchemy import delete
        await self.execute(
            delete(MtClientChannel).where(MtClientChannel.client_id == client_id)
        )
