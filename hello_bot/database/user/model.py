import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from hello_bot.database import Base


class User(Base):
    """Модель пользователя hello_bot."""

    __tablename__ = "users"

    # Data
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
    channel_id: Mapped[int | None] = mapped_column(BigInteger)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_approved: Mapped[bool] = mapped_column(default=False)
    time_approved: Mapped[int | None] = mapped_column(default=None)
    walk_captcha: Mapped[bool] = mapped_column(default=False)
    time_walk_captcha: Mapped[int | None] = mapped_column(default=None)
    captcha_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    invite_url: Mapped[str | None] = mapped_column(default=None)
