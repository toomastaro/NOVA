"""
Модель данных для постов бота.
"""

import time

from sqlalchemy import JSON, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import Status


class BotPost(Base):
    """
    Модель поста для рассылки через бота.

    Атрибуты:
        id (int): Уникальный ID поста.
        chat_ids (list[int]): Список ID чатов/пользователей для рассылки.
        admin_id (int): ID администратора, создавшего пост.
        message (dict): Содержимое сообщения (JSON).
        send_time (int): Запланированное время отправки.
        delete_time (int): Время для автоудаления.
        report (bool): Флаг необходимости отчета.
        text_with_name (bool): Флаг добавления имени в текст.
        created_timestamp (int): Время создания.
        backup_chat_id (int): ID резервного канала (для копии).
        backup_message_id (int): ID сообщения в резерве.
        status (Status): Текущий статус рассылки.
        start_timestamp (int): Время начала рассылки.
        end_timestamp (int): Время окончания.
        success_send (int): Количество успешных отправок.
        error_send (int): Количество ошибок.
        message_ids (dict): Сохраненные ID отправленных сообщений (для удаления).
    """

    __tablename__ = "bot_posts"

    # Данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    chat_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    send_time: Mapped[int | None] = mapped_column(index=True, default=None)
    delete_time: Mapped[int | None] = mapped_column(default=None)

    report: Mapped[bool] = mapped_column(default=False)
    text_with_name: Mapped[bool] = mapped_column(default=False)

    created_timestamp: Mapped[int] = mapped_column(default=time.time)

    # Бэкап
    backup_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)

    # Данные отчета
    status: Mapped[Status] = mapped_column(default=Status.PENDING)
    start_timestamp: Mapped[int | None] = mapped_column(default=None)
    end_timestamp: Mapped[int | None] = mapped_column(default=None)
    success_send: Mapped[int] = mapped_column(default=0)
    error_send: Mapped[int] = mapped_column(default=0)
    message_ids: Mapped[dict | None] = mapped_column(JSON, default=None)
    deleted_at: Mapped[int | None] = mapped_column(default=None)
