"""
Модель данных для капчи/приветствия в канале.
"""

from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ChannelCaptcha(Base):
    """
    Модель сообщения капчи (приветствия) для канала.

    Атрибуты:
        id (int): Уникальный ID.
        channel_id (int): ID канала (Telegram Chat ID).
        message (dict): Сообщение (JSON).
        delay (int): Задержка отправки в секундах.
    """
    __tablename__ = "channel_captcha"

    # Data
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    delay: Mapped[int] = mapped_column(default=0)
