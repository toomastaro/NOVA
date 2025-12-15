import logging
from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_settings.model import ChannelBotSetting
from sqlalchemy import insert, select, update

logger = logging.getLogger(__name__)


class ChannelBotSettingCrud(DatabaseMixin):
    async def add_channel_bot_setting(self, **kwargs):
        await self.execute(insert(ChannelBotSetting).values(**kwargs))

    async def update_channel_bot_setting(self, chat_id: int, **kwargs):
        await self.execute(
            update(ChannelBotSetting)
            .where(ChannelBotSetting.id == chat_id)
            .values(**kwargs)
        )

    async def get_channel_bot_setting(self, chat_id: int) -> ChannelBotSetting:
        return await self.fetchrow(
            select(ChannelBotSetting).where(ChannelBotSetting.id == chat_id)
        )

    async def get_all_channels_in_bot_id(self, bot_id: int):
        return await self.fetch(
            select(ChannelBotSetting).where(ChannelBotSetting.bot_id == bot_id)
        )

    async def get_bot_channels(self, admin_id: int):
        return await self.fetch(
            select(ChannelBotSetting).where(ChannelBotSetting.admin_id == admin_id)
        )
