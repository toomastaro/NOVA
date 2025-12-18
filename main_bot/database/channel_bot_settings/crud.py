"""
Модуль операций базы данных для настроек бота в канале.
"""

import logging

from sqlalchemy import insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_settings.model import ChannelBotSetting

logger = logging.getLogger(__name__)


class ChannelBotSettingCrud(DatabaseMixin):
    """
    Класс для управления настройками бота в каналах.
    """

    async def add_channel_bot_setting(self, **kwargs) -> None:
        """
        Добавляет настройки для канала.

        Аргументы:
            **kwargs: Поля модели ChannelBotSetting.
        """
        await self.execute(insert(ChannelBotSetting).values(**kwargs))

    async def update_channel_bot_setting(self, chat_id: int, **kwargs) -> None:
        """
        Обновляет настройки канала.

        Аргументы:
            chat_id (int): ID канала.
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(ChannelBotSetting)
            .where(ChannelBotSetting.id == chat_id)
            .values(**kwargs)
        )

    async def get_channel_bot_setting(self, chat_id: int) -> ChannelBotSetting | None:
        """
        Получает настройки канала.

        Аргументы:
            chat_id (int): ID канала.
        """
        return await self.fetchrow(
            select(ChannelBotSetting).where(ChannelBotSetting.id == chat_id)
        )

    async def get_all_channels_in_bot_id(self, bot_id: int) -> list:
        """
        Получает все каналы, подключенные к определенному боту (из настроек).

        Аргументы:
            bot_id (int): ID бота.
        """
        return await self.fetch(
            select(ChannelBotSetting).where(ChannelBotSetting.bot_id == bot_id)
        )

    async def get_bot_channels(self, admin_id: int, only_with_bot: bool = False) -> list:
        """
        Получает все настройки каналов для админа.

        Аргументы:
            admin_id (int): ID администратора.
            only_with_bot (bool): Если True, возвращает только каналы с привязанным ботом.
        """
        stmt = select(ChannelBotSetting).where(ChannelBotSetting.admin_id == admin_id)
        if only_with_bot:
            stmt = stmt.where(
                ChannelBotSetting.bot_id.is_not(None), ChannelBotSetting.bot_id != 0
            )

        return await self.fetch(stmt)
