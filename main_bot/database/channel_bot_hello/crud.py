"""
Модуль операций базы данных для приветственных сообщений.
"""

import logging

from sqlalchemy import asc, delete, func, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.channel_bot_hello.model import ChannelHelloMessage

logger = logging.getLogger(__name__)


class ChannelHelloMessageCrud(DatabaseMixin):
    """
    Класс для управления приветственными сообщениями канала.
    """

    async def get_next_id_hello_message(self) -> int:
        """
        Получает следующий доступный ID для сообщения (autoincrement emulation).

        Возвращает:
            int: Следующий ID (max + 1).
        """
        max_id = await self.fetchrow(select(func.max(ChannelHelloMessage.id)))

        if not max_id:
            max_id = 0

        return max_id + 1

    async def add_channel_hello_message(self, **kwargs) -> None:
        """
        Добавляет новое приветственное сообщение.

        Аргументы:
            **kwargs: Поля модели ChannelHelloMessage.
        """
        await self.execute(insert(ChannelHelloMessage).values(**kwargs))

    async def get_hello_messages(self, chat_id: int, active: bool = False) -> list:
        """
        Получает список приветственных сообщений для канала.

        Аргументы:
            chat_id (int): ID канала.
            active (bool): Если True, только активные сообщения.
        """
        stmt = (
            select(ChannelHelloMessage)
            .where(ChannelHelloMessage.channel_id == chat_id)
            .order_by(asc(ChannelHelloMessage.id))
        )

        if active:
            stmt = stmt.where(ChannelHelloMessage.is_active.is_(True))

        return await self.fetch(stmt)

    async def get_hello_message(self, message_id: int) -> ChannelHelloMessage | None:
        """
        Получает сообщение по ID.
        """
        return await self.fetchrow(
            select(ChannelHelloMessage).where(ChannelHelloMessage.id == message_id)
        )

    async def update_hello_message(
        self, message_id: int, return_obj: bool = False, **kwargs
    ) -> ChannelHelloMessage | None:
        """
        Обновляет приветственное сообщение.

        Аргументы:
            message_id (int): ID сообщения.
            return_obj (bool): Вернуть ли обновленный объект.
            **kwargs: Поля для обновления.
        """
        stmt = (
            update(ChannelHelloMessage)
            .where(ChannelHelloMessage.id == message_id)
            .values(**kwargs)
        )

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ChannelHelloMessage)
        else:
            operation = self.execute

        return await operation(stmt, **{"commit": return_obj} if return_obj else {})

    async def delete_hello_message(self, message_id: int) -> None:
        """
        Удаляет приветственное сообщение.
        """
        await self.execute(
            delete(ChannelHelloMessage).where(ChannelHelloMessage.id == message_id)
        )
