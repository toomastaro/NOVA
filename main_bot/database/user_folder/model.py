"""
Модель данных папки пользователя для группировки каналов/чатов.
"""

from sqlalchemy import ARRAY, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import FolderType


class UserFolder(Base):
    """
    Модель папки пользователя.

    Используется для организации каналов и чатов в группы.

    Атрибуты:
        id (int): Уникальный ID папки.
        user_id (int): ID владельца (пользователя Telegram).
        title (str): Название папки.
        type (FolderType): Тип папки (например, CHANNEL).
        content (list): Список ID каналов/чатов в папке.
    """
    __tablename__ = "user_folders"

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column()
    type: Mapped[FolderType] = mapped_column()
    content: Mapped[list] = mapped_column(ARRAY(String), default=[])
