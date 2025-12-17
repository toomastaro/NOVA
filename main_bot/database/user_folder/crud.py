"""
Модуль операций базы данных для папок пользователя.
"""

import logging

from sqlalchemy import delete, insert, select, update

from main_bot.database import DatabaseMixin
from main_bot.database.db_types import FolderType
from main_bot.database.user_folder.model import UserFolder

logger = logging.getLogger(__name__)


class UserFolderCrud(DatabaseMixin):
    """
    Класс для управления папками пользователей.
    """

    async def add_folder(self, **kwargs) -> None:
        """
        Добавляет новую папку.

        Аргументы:
            **kwargs: Поля модели UserFolder.
        """
        await self.execute(insert(UserFolder).values(**kwargs))

    async def remove_folder(self, folder_id: int) -> None:
        """
        Удаляет папку по ID.
        """
        await self.execute(delete(UserFolder).where(UserFolder.id == folder_id))

    async def get_folder_by_id(self, folder_id: int) -> UserFolder | None:
        """
        Получает папку по ID.
        """
        return await self.fetchrow(select(UserFolder).where(UserFolder.id == folder_id))

    async def update_folder(self, folder_id: int, **kwargs) -> None:
        """
        Обновляет данные папки.

        Аргументы:
            folder_id (int): ID папки.
            **kwargs: Поля для обновления.
        """
        await self.execute(
            update(UserFolder).where(UserFolder.id == folder_id).values(**kwargs)
        )

    async def get_folders(
        self, user_id: int, folder_type: FolderType = FolderType.CHANNEL
    ) -> list:
        """
        Получает список папок пользователя определенного типа.

        Аргументы:
            user_id (int): ID пользователя.
            folder_type (FolderType): Тип папки.

        Возвращает:
            list[UserFolder]: Список папок.
        """
        return await self.fetch(
            select(UserFolder)
            .where(UserFolder.user_id == user_id, UserFolder.type == folder_type)
            .order_by(UserFolder.title)
        )

    async def get_folder_by_title(self, title: str, user_id: int) -> UserFolder | None:
        """
        Получает папку по названию и ID пользователя.
        """
        return await self.fetchrow(
            select(UserFolder).where(
                UserFolder.title == title, UserFolder.user_id == user_id
            )
        )
