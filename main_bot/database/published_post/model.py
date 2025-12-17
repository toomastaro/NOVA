"""
Модель данных опубликованного поста.
"""

import time
from typing import List, Optional

from sqlalchemy import JSON, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class PublishedPost(Base):
    """
    Модель опубликованного поста (хранит историю и статистику).

    Атрибуты:
        id (int): Уникальный ID записи (PK).
        post_id (int): ID родительского поста (Post.id).
        message_id (int): ID сообщения в канале Telegram.
        chat_id (int): ID канала/чата.
        admin_id (int): ID админа, опубликовавшего пост.
        message_options (dict): Контент сообщения.
        reaction (dict | None): Реакции.
        hide (List[dict] | None): Скрытый контент.
        buttons (str | None): Кнопки.
        unpin_time (int | None): Время автоматического открепления.
        delete_time (int | None): Время автоматического удаления.
        report (bool): Включен ли отчет.
        cpm_price (int | None): Цена CPM.
        backup_chat_id (int | None): ID бэкап-канала.
        backup_message_id (int | None): ID бэкап-сообщения.
        created_timestamp (int): Время публикации.
        status (str): Статус ('active' или 'deleted').
        deleted_at (int | None): Время удаления.
        views_24h (int | None): Просмотры через 24ч.
        views_48h (int | None): Просмотры через 48ч.
        views_72h (int | None): Просмотры через 72ч.
        report_24h_sent (bool): Отчет 24ч отправлен.
        report_48h_sent (bool): Отчет 48ч отправлен.
        report_72h_sent (bool): Отчет 72ч отправлен.
    """

    __tablename__ = "published_posts"

    # Основные данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(index=True, comment="ID родительского поста")
    message_id: Mapped[int] = mapped_column(
        BigInteger, index=True, comment="ID сообщения в канале"
    )
    chat_id: Mapped[int] = mapped_column(
        BigInteger, index=True, comment="ID канала/чата"
    )
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="ID админа")

    message_options: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Контент сообщения"
    )
    reaction: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="Реакции"
    )
    hide: Mapped[Optional[List[dict]]] = mapped_column(
        ARRAY(JSON), default=None, comment="Скрытый контент"
    )
    buttons: Mapped[Optional[str]] = mapped_column(comment="Кнопки")

    unpin_time: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Время открепа (если было закреплено)"
    )
    delete_time: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Время автоудаления"
    )
    report: Mapped[bool] = mapped_column(default=False, comment="Включен ли отчет")
    cpm_price: Mapped[Optional[int]] = mapped_column(default=None, comment="Цена CPM")

    backup_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)

    created_timestamp: Mapped[int] = mapped_column(
        default=lambda: int(time.time()), comment="Время публикации"
    )
    status: Mapped[str] = mapped_column(
        default="active", comment="Статус (active/deleted)"
    )
    deleted_at: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Время удаления"
    )

    # Данные отчетов CPM (Views Reporting)
    views_24h: Mapped[Optional[int]] = mapped_column(default=0)
    views_48h: Mapped[Optional[int]] = mapped_column(default=0)
    views_72h: Mapped[Optional[int]] = mapped_column(default=0)
    report_24h_sent: Mapped[bool] = mapped_column(default=False)
    report_48h_sent: Mapped[bool] = mapped_column(default=False)
    report_72h_sent: Mapped[bool] = mapped_column(default=False)
