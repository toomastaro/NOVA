import time

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Channel(Base):
    __tablename__ = 'channels'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    title: Mapped[str] = mapped_column(String(64), nullable=False)
    admin_id: Mapped[int] = mapped_column(BigInteger)
    subscribe: Mapped[int | None] = mapped_column()
    session_path: Mapped[str | None] = mapped_column()
    emoji_id: Mapped[str] = mapped_column(nullable=False)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
    
    # Round-robin distribution field
    last_client_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True, default=None)
