"""
Модель данных сторис (для планировщика).
"""

import time

from sqlalchemy import JSON, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import Status


class Story(Base):
    """
    Модель сторис.

    Атрибуты:
        id (int): Уникальный ID записи.
        chat_ids (list): Список ID чатов/каналов для публикации.
        admin_id (int): ID админа, создавшего сторис.
        story_options (dict): Контент сторис (медиа, подписи).
        send_time (int | None): Время запланированной отправки.
        report (bool): Включен ли отчет.
        created_timestamp (int): Время создания.
        backup_chat_id (int | None): ID бэкап-канала.
        backup_message_id (int | None): ID бэкап-сообщения.
        status (Status): Статус публикации (PENDING, FINISH, ERROR).
        delete_time (int | None): Время автоудаления.
    """
    __tablename__ = "stories"

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_ids: Mapped[list] = mapped_column(ARRAY(BigInteger), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    story_options: Mapped[dict] = mapped_column(JSON, nullable=False)
    send_time: Mapped[int | None] = mapped_column(index=True)

    report: Mapped[bool] = mapped_column(default=False)
    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()))

    # Backup & Status
    backup_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    status: Mapped[Status] = mapped_column(default=Status.PENDING)
    delete_time: Mapped[int | None] = mapped_column(default=None)
