"""
Модуль операций базы данных для капчи канала.
"""

import logging

from sqlalchemy import asc, delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_captcha.model import ChannelCaptcha

logger = logging.getLogger(__name__)


class ChannelCaptchaMessageCrud(DatabaseMixin):
    """
    Класс для управления сообщениями капчи.
    """

    async def add_channel_captcha(
        self, return_obj: bool = False, **kwargs
    ) -> ChannelCaptcha | None:
        """
        Создает новое сообщение капчи.

        Аргументы:
            return_obj (bool): Вернуть ли созданный объект.
            **kwargs: Поля модели ChannelCaptcha.
        """
        stmt = insert(ChannelCaptcha).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ChannelCaptcha)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def get_all_captcha(self, chat_id: int) -> list:
        """
        Получает все сообщения капчи для канала.

        Аргументы:
            chat_id (int): ID канала.
        """
        return await self.fetch(
            select(ChannelCaptcha)
            .where(ChannelCaptcha.channel_id == chat_id)
            .order_by(asc(ChannelCaptcha.id))
        )

    async def get_captcha(self, message_id: int) -> ChannelCaptcha | None:
        """
        Получает конкретное сообщение капчи по ID.
        """
        return await self.fetchrow(
            select(ChannelCaptcha).where(ChannelCaptcha.id == message_id)
        )

    async def update_captcha(
        self, captcha_id: int, return_obj: bool = False, **kwargs
    ) -> ChannelCaptcha | None:
        """
        Обновляет сообщение капчи.

        Аргументы:
            captcha_id (int): ID сообщения.
            return_obj (bool): Вернуть ли обновленный объект.
            **kwargs: Поля для обновления.
        """
        stmt = (
            update(ChannelCaptcha)
            .where(ChannelCaptcha.id == captcha_id)
            .values(**kwargs)
        )

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ChannelCaptcha)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_captcha(self, message_id: int) -> None:
        """
        Удаляет сообщение капчи.
        """
        await self.execute(
            delete(ChannelCaptcha).where(ChannelCaptcha.id == message_id)
        )
