import time

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class UserBot(Base):
    __tablename__ = 'user_bots'

    # Data
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    schema: Mapped[str] = mapped_column(String, nullable=False)

    title: Mapped[str] = mapped_column(nullable=False)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    token: Mapped[str] = mapped_column(String(256), nullable=False)
    subscribe: Mapped[int | None] = mapped_column(default=None)
    emoji_id: Mapped[str] = mapped_column(nullable=False)

    created_timestamp: Mapped[int] = mapped_column(default=time.time)
