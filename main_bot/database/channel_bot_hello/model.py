"""
Модель данных для приветственного сообщения канала.
"""

from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ChannelHelloMessage(Base):
    """
    Модель приветственного сообщения в канале (Hello Message).

    Атрибуты:
        id (int): Уникальный ID.
        channel_id (int): ID канала (Telegram Chat ID).
        message (dict): Содержимое сообщения (JSON).
        delay (int): Задержка отправки в секундах.
        text_with_name (bool): Подставлять ли имя пользователя.
        is_active (bool): Активно ли сообщение.
    """

    __tablename__ = "channel_hello_messages"

    # Данные
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    delay: Mapped[int] = mapped_column(default=0)
    text_with_name: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
