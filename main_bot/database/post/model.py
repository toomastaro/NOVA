"""
Модель данных поста (планировщик).
"""

import time
from typing import List, Optional

from sqlalchemy import JSON, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Post(Base):
    """
    Модель поста (черновик или запланированный).

    Атрибуты:
        id (int): Уникальный ID поста (PK).
        chat_ids (List[int]): Список ID чатов/каналов для публикации.
        admin_id (int): ID админа, создавшего пост.
        message_options (dict): Контент сообщения (текст, медиа, разметка).
        buttons (str | None): JSON-строка с клавиатурой.
        send_time (int | None): Время запланированной отправки (UNIX timestamp).
        reaction (dict | None): Настройки реакций.
        hide (List[dict] | None): Скрытый контент (спойлеры).
        pin_time (int | None): Время закрепления в канале.
        delete_time (int | None): Время автоудаления из канала.
        report (bool): Включен ли отчет о просмотре (CPM).
        cpm_price (int | None): Цена за просмотр (если это реклама).
        backup_chat_id (int | None): ID чата для бэкапа (если удалили).
        backup_message_id (int | None): ID сообщения в бэкапе.
        views_24h (int | None): Просмотры за 24ч (для отчета).
        views_48h (int | None): Просмотры за 48ч.
        views_72h (int | None): Просмотры за 72ч.
        report_24h_sent (bool): Отправлен ли отчет за 24ч.
        report_48h_sent (bool): Отправлен ли отчет за 48ч.
        report_72h_sent (bool): Отправлен ли отчет за 72ч.
        created_timestamp (int): Время создания поста.
    """

    __tablename__ = "posts"

    # Основные данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_ids: Mapped[List[int]] = mapped_column(
        ARRAY(BigInteger), index=True, comment="Список ID чатов/каналов"
    )
    admin_id: Mapped[int] = mapped_column(
        BigInteger, index=True, comment="ID админа, создавшего пост"
    )

    message_options: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="Контент сообщения (текст, медиа и т.д.)"
    )
    buttons: Mapped[Optional[str]] = mapped_column(comment="JSON-строка с кнопками")
    send_time: Mapped[Optional[int]] = mapped_column(
        index=True, default=None, comment="Время запланированной отправки (timestamp)"
    )

    reaction: Mapped[Optional[dict]] = mapped_column(
        JSON, default=None, comment="Настройки реакций"
    )
    hide: Mapped[Optional[List[dict]]] = mapped_column(
        ARRAY(JSON), default=None, comment="Скрытый контент (спойлеры и т.д.)"
    )

    pin_time: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Время закрепа"
    )
    delete_time: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Время автоудаления"
    )
    report: Mapped[bool] = mapped_column(default=False, comment="Включен ли отчет")
    cpm_price: Mapped[Optional[int]] = mapped_column(
        default=None, comment="Цена за CPM (если реклама)"
    )

    backup_chat_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="ID чата для бэкапа"
    )
    backup_message_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="ID сообщения в бэкапе"
    )

    # Данные отчетов CPM (Views Reporting)
    views_24h: Mapped[Optional[int]] = mapped_column(default=None)
    views_48h: Mapped[Optional[int]] = mapped_column(default=None)
    views_72h: Mapped[Optional[int]] = mapped_column(default=None)
    report_24h_sent: Mapped[bool] = mapped_column(default=False)
    report_48h_sent: Mapped[bool] = mapped_column(default=False)
    report_72h_sent: Mapped[bool] = mapped_column(default=False)

    created_timestamp: Mapped[int] = mapped_column(
        default=lambda: int(time.time()), comment="Время создания"
    )
