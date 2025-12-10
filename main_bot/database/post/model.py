import time
from typing import List, Optional

from sqlalchemy import BigInteger, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Post(Base):
    """
    Модель поста (черновик или запланированный).
    """
    __tablename__ = 'posts'

    # Основные данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_ids: Mapped[List[int]] = mapped_column(ARRAY(BigInteger), index=True, comment='Список ID чатов/каналов')
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True, comment='ID админа, создавшего пост')

    message_options: Mapped[dict] = mapped_column(JSON, nullable=False, comment='Контент сообщения (текст, медиа и т.д.)')
    buttons: Mapped[Optional[str]] = mapped_column(comment='JSON-строка с кнопками')
    send_time: Mapped[Optional[int]] = mapped_column(index=True, default=None, comment='Время запланированной отправки (timestamp)')

    reaction: Mapped[Optional[dict]] = mapped_column(JSON, default=None, comment='Настройки реакций')
    hide: Mapped[Optional[List[dict]]] = mapped_column(ARRAY(JSON), default=None, comment='Скрытый контент (спойлеры и т.д.)')

    pin_time: Mapped[Optional[int]] = mapped_column(default=None, comment='Время закрепа')
    delete_time: Mapped[Optional[int]] = mapped_column(default=None, comment='Время автоудаления')
    report: Mapped[bool] = mapped_column(default=False, comment='Включен ли отчет')
    cpm_price: Mapped[Optional[int]] = mapped_column(default=None, comment='Цена за CPM (если реклама)')

    backup_chat_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment='ID чата для бэкапа')
    backup_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment='ID сообщения в бэкапе')

    # Данные отчетов CPM (Views Reporting)
    views_24h: Mapped[Optional[int]] = mapped_column(default=None)
    views_48h: Mapped[Optional[int]] = mapped_column(default=None)
    views_72h: Mapped[Optional[int]] = mapped_column(default=None)
    report_24h_sent: Mapped[bool] = mapped_column(default=False)
    report_48h_sent: Mapped[bool] = mapped_column(default=False)
    report_72h_sent: Mapped[bool] = mapped_column(default=False)

    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()), comment='Время создания')
