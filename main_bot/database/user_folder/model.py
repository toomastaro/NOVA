from sqlalchemy import BigInteger, String, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.types import FolderType


class UserFolder(Base):
    __tablename__ = 'user_folders'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    title: Mapped[str] = mapped_column()
    type: Mapped[FolderType] = mapped_column()
    content: Mapped[list] = mapped_column(ARRAY(String), default=[])
