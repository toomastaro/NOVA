"""
Модель данных для постоянного хранения внешних каналов в Novastat.
"""

import time
from typing import Optional

from sqlalchemy import BigInteger, Boolean, String, Integer
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ExternalChannel(Base):
    """
    Модель внешнего Telegram-канала.
    
    Используется для кэширования и периодического обновления статистики
    по каналам, которые не добавлены в систему как 'свои'.
    """

    __tablename__ = "external_channels"

    chat_id: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, comment="Telegram ID канала (с -100)"
    )
    title: Mapped[str] = mapped_column(
        String(255), nullable=False, comment="Название канала"
    )
    username: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Юзернейм канала"
    )
    invite_link: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True, comment="Приватная ссылка приглашения"
    )
    last_requested_at: Mapped[int] = mapped_column(
        BigInteger, default=lambda: int(time.time()), comment="Последний запрос от пользователя"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, default=True, comment="Флаг активности (опрашиваем ли раз в 3 часа)"
    )
    
    pinned_client_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, default=None, comment="ID клиента, который успешно вступил/проверил канал"
    )
    
    # Статистика
    subscribers_count: Mapped[int] = mapped_column(
        Integer, default=0, comment="Количество подписчиков"
    )
    novastat_24h: Mapped[int] = mapped_column(
        Integer, default=0, comment="Просмотры за 24ч"
    )
    novastat_48h: Mapped[int] = mapped_column(
        Integer, default=0, comment="Просмотры за 48ч"
    )
    novastat_72h: Mapped[int] = mapped_column(
        Integer, default=0, comment="Просмотры за 72ч"
    )
    
    updated_at: Mapped[int] = mapped_column(
        BigInteger, default=lambda: int(time.time()), comment="Последнее обновление статистики"
    )
