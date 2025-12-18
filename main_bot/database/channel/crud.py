"""
Модуль операций базы данных для Telegram-каналов.
"""

import logging
from typing import List, Literal

from sqlalchemy import desc, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from config import Config
from main_bot.database import DatabaseMixin
from main_bot.database.channel.model import Channel

import time

logger = logging.getLogger(__name__)


class ChannelCrud(DatabaseMixin):
    """
    Класс для управления Telegram-каналами (Channel).
    """

    async def get_subscribe_channels(self, user_id: int) -> List[Channel]:
        """
        Получает список каналов пользователя с активной подпиской.

        Аргументы:
            user_id (int): ID пользователя (админа).

        Возвращает:
            List[Channel]: Список каналов.
        """
        return await self.fetch(
            select(Channel).where(
                Channel.admin_id == user_id,
                Channel.subscribe.is_not(None),
                Channel.subscribe != Config.SOFT_DELETE_TIMESTAMP,
            )
        )

    async def get_user_channels(
        self,
        user_id: int,
        limit: int = None,
        sort_by: Literal["subscribe"] = None,
        from_array: List[int] = None,
    ) -> List[Channel]:
        """
        Получает список каналов пользователя с опциональной фильтрацией и сортировкой.

        Аргументы:
            user_id (int): ID пользователя.
            limit (int, optional): Лимит количества (для пагинации).
            sort_by (Literal['subscribe'], optional): Поле сортировки.
            from_array (List[int], optional): Список chat_id для фильтрации.

        Возвращает:
            List[Channel]: Список каналов.
        """
        stmt = select(Channel).where(
            Channel.admin_id == user_id,
            Channel.subscribe != Config.SOFT_DELETE_TIMESTAMP,
        )

        if sort_by:
            stmt = stmt.order_by(desc(Channel.subscribe))

        if limit:
            stmt = stmt.limit(limit)
        if from_array:
            stmt = stmt.where(Channel.chat_id.in_(from_array))

        return await self.fetch(stmt)

    async def get_channel_by_row_id(self, row_id: int) -> Channel | None:
        """
        Получает канал по его первичному ключу (ID в БД).

        Аргументы:
            row_id (int): Внутренний ID канала.
        """
        return await self.fetchrow(select(Channel).where(Channel.id == row_id))

    async def get_channel_admin_row(self, chat_id: int, user_id: int) -> Channel | None:
        """
        Получает канал по chat_id и admin_id.
        Проверяет владение каналом конкретным пользователем.

        Аргументы:
            chat_id (int): ID канала в Telegram.
            user_id (int): ID пользователя.
        """
        return await self.fetchrow(
            select(Channel).where(
                Channel.chat_id == chat_id, Channel.admin_id == user_id
            )
        )

    async def get_channel_by_chat_id(self, chat_id: int) -> Channel | None:
        """
        Получает канал по Telegram chat_id.

        Аргументы:
            chat_id (int): ID канала в Telegram.
        """
        return await self.fetchrow(
            select(Channel).where(Channel.chat_id == chat_id).limit(1)
        )

    async def update_channel_by_chat_id(self, chat_id: int, **kwargs) -> None:
        """
        Обновляет данные канала по chat_id.

        Аргументы:
            chat_id (int): ID канала в Telegram.
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(Channel).where(Channel.chat_id == chat_id).values(**kwargs)
        )

    async def update_channel_by_id(self, channel_id: int, **kwargs) -> None:
        """
        Обновляет данные канала по ID (Primary Key).

        Аргументы:
            channel_id (int): Внутренний ID канала.
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(Channel).where(Channel.id == channel_id).values(**kwargs)
        )

    async def add_channel(self, **kwargs) -> None:
        """
        Добавляет или восстанавливает канал.
        Реализует логику пробного периода (Trial).
        """
        chat_id = kwargs.get("chat_id")
        admin_id = kwargs.get("admin_id")

        # 1. Проверяем, был ли канал в базе ВООБЩЕ (для Trial проверяем только по chat_id)
        # Существование записи гарантирует, что кто-то уже добавлял этот канал
        existing_any_admin = await self.fetchrow(
            select(Channel).where(Channel.chat_id == chat_id).limit(1)
        )

        # 2. Если канала нет совсем и включен Trial — начисляем дни
        if not existing_any_admin and Config.TRIAL:
            trial_end = int(time.time()) + (Config.TRIAL_DAYS * 86400)
            kwargs["subscribe"] = trial_end
            logger.info(
                f"Начислен Trial ({Config.TRIAL_DAYS} дн.) для нового канала {chat_id}"
            )

        # 3. Добавляем/обновляем запись для конкретного админа
        stmt = pg_insert(Channel).values(**kwargs)

        # При конфликте (если запись уже есть для этого админа)
        # Если канал был "удален" (метка 2000 года), снимаем метку
        update_values = kwargs.copy()

        # Проверяем, была ли метка удаления у текущего админа
        existing_for_admin = await self.fetchrow(
            select(Channel).where(
                Channel.chat_id == chat_id, Channel.admin_id == admin_id
            )
        )

        if (
            existing_for_admin
            and existing_for_admin.subscribe == Config.SOFT_DELETE_TIMESTAMP
        ):
            # Восстановление: если подписки нет, ставим None, чтобы не висел 2000 год
            if (
                "subscribe" not in update_values
                or update_values["subscribe"] == Config.SOFT_DELETE_TIMESTAMP
            ):
                update_values["subscribe"] = None

        stmt = stmt.on_conflict_do_update(
            index_elements=["chat_id", "admin_id"], set_=update_values
        )
        await self.execute(stmt)

    async def delete_channel(self, chat_id: int, user_id: int = None) -> None:
        """
        Мягкое удаление канала (установка даты подписки на 01.01.2000).
        """
        stmt = (
            update(Channel)
            .where(Channel.chat_id == chat_id)
            .values(subscribe=Config.SOFT_DELETE_TIMESTAMP)
        )
        if user_id:
            stmt = stmt.where(Channel.admin_id == user_id)

        await self.execute(stmt)

    async def get_active_channels(self) -> List[Channel]:
        """
        Получает все каналы с активной подпиской (системный метод).
        """
        stmt = (
            select(Channel)
            .where(
                Channel.subscribe.is_not(None),
                Channel.subscribe != Config.SOFT_DELETE_TIMESTAMP,
            )
            .order_by(Channel.id.asc())
        )
        return await self.fetch(stmt)

    async def get_user_channels_without_folders(self, user_id: int) -> List[Channel]:
        """
        Получает каналы пользователя, которые НЕ находятся ни в одной папке.

        Аргументы:
            user_id (int): ID пользователя.
        """
        from main_bot.database.db_types import FolderType
        from main_bot.database.user_folder.model import UserFolder

        # Получаем все chat_ids из папок пользователя
        stmt_folders = select(UserFolder.content).where(
            UserFolder.user_id == user_id, UserFolder.type == FolderType.CHANNEL
        )
        folders_content = await self.fetch(stmt_folders)

        # Разворачиваем список списков
        excluded_chat_ids = []
        for content in folders_content:
            if content:
                excluded_chat_ids.extend([int(c) for c in content])

        # Получаем каналы, которых нет в исключенных и которые не удалены
        stmt = select(Channel).where(
            Channel.admin_id == user_id,
            Channel.subscribe != Config.SOFT_DELETE_TIMESTAMP,
        )

        if excluded_chat_ids:
            stmt = stmt.where(Channel.chat_id.notin_(excluded_chat_ids))

        return await self.fetch(stmt)

    async def update_last_client(self, channel_id: int, client_id: int) -> None:
        """
        Обновить last_client_id для канала (для round-robin распределения).

        Аргументы:
            channel_id (int): ID канала (row id, не chat_id).
            client_id (int): ID клиента.
        """
        await self.execute(
            update(Channel)
            .where(Channel.id == channel_id)
            .values(last_client_id=client_id)
        )

    async def get_all_channels(self) -> List[Channel]:
        """
        Получить все каналы (для админ-панели и шедулера), исключая дубликаты.
        """
        # Используем DISTINCT ON (postgres only) для выбора уникальных каналов
        # Сортировка по chat_id обязательна для distinct on
        stmt = (
            select(Channel)
            .where(Channel.subscribe != Config.SOFT_DELETE_TIMESTAMP)
            .distinct(Channel.chat_id)
            .order_by(Channel.chat_id, Channel.id.desc())
        )
        return await self.fetch(stmt)

    async def get_channels(self) -> List[Channel]:
        """Alias for get_all_channels"""
        return await self.get_all_channels()

    async def get_channel_by_id(self, channel_id: int) -> Channel | None:
        """Получить канал по ID (row_id)"""
        return await self.get_channel_by_row_id(channel_id)
