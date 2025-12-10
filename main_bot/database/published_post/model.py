import time
from typing import List, Optional

from sqlalchemy import BigInteger, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class PublishedPost(Base):
    """
    Модель опубликованного поста (хранит историю и статистику).
    """
    __tablename__ = 'published_posts'

    # Основные данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(index=True, comment='ID родительского поста')
    message_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='ID сообщения в канале')
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='ID канала/чата')
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='ID админа')

    message_options: Mapped[dict] = mapped_column(JSON, nullable=False, comment='Контент сообщения')
    reaction: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment='Реакции')
    hide: Mapped[Optional[List[dict]]] = mapped_column(ARRAY(JSON), default=None, comment='Скрытый контент')
    buttons: Mapped[Optional[str]] = mapped_column(comment='Кнопки')

    unpin_time: Mapped[Optional[int]] = mapped_column(default=None, comment='Время открепа (если было закреплено)')
    delete_time: Mapped[Optional[int]] = mapped_column(default=None, comment='Время автоудаления')
    report: Mapped[bool] = mapped_column(default=False, comment='Включен ли отчет')
    cpm_price: Mapped[Optional[int]] = mapped_column(default=None, comment='Цена CPM')

    backup_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None)

    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()), comment='Время публикации')
    status: Mapped[str] = mapped_column(default='active', comment='Статус (active/deleted)')
    deleted_at: Mapped[Optional[int]] = mapped_column(default=None, comment='Время удаления')

    # Данные отчетов CPM (Views Reporting)
    views_24h: Mapped[Optional[int]] = mapped_column(default=None)
    views_48h: Mapped[Optional[int]] = mapped_column(default=None)
    views_72h: Mapped[Optional[int]] = mapped_column(default=None)
    report_24h_sent: Mapped[bool] = mapped_column(default=False)
    report_48h_sent: Mapped[bool] = mapped_column(default=False)
    report_72h_sent: Mapped[bool] = mapped_column(default=False)
