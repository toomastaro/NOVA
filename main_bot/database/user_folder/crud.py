import logging
from main_bot.database import DatabaseMixin
from main_bot.database.db_types import FolderType
from main_bot.database.user_folder.model import UserFolder
from sqlalchemy import delete, insert, select, update

logger = logging.getLogger(__name__)


class UserFolderCrud(DatabaseMixin):
    async def add_folder(self, **kwargs):
        await self.execute(insert(UserFolder).values(**kwargs))

    async def remove_folder(self, folder_id: int):
        await self.execute(delete(UserFolder).where(UserFolder.id == folder_id))

    async def get_folder_by_id(self, folder_id: int) -> UserFolder:
        return await self.fetchrow(select(UserFolder).where(UserFolder.id == folder_id))

    async def update_folder(self, folder_id: int, **kwargs):
        await self.execute(
            update(UserFolder).where(UserFolder.id == folder_id).values(**kwargs)
        )

    async def get_folders(
        self, user_id: int, folder_type: FolderType = FolderType.CHANNEL
    ):
        return await self.fetch(
            select(UserFolder)
            .where(UserFolder.user_id == user_id, UserFolder.type == folder_type)
            .order_by(UserFolder.title)
        )

    async def get_folder_by_title(self, title: str, user_id: int) -> UserFolder:
        return await self.fetchrow(
            select(UserFolder).where(
                UserFolder.title == title, UserFolder.user_id == user_id
            )
        )
