"""
Модели данных для рекламных креативов.

Описывает таблицы для хранения рекламных объявлений (AdCreative)
и ссылочных слотов (AdCreativeLinkSlot).
"""

import time

from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class AdCreative(Base):
    """
    Модель рекламного креатива.

    Атрибуты:
        id (int): Уникальный идентификатор.
        owner_id (int): ID владельца (Telegram ID).
        name (str): Название креатива.
        raw_message (dict): Сырое сообщение (структура Telegram).
        created_timestamp (int): Время создания.
        status (str): Статус креатива (active, deleted).
    """
    __tablename__ = "ad_creatives"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column()
    # Сырые данные сообщения для пересылки/копирования
    raw_message: Mapped[dict] = mapped_column(JSON)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
    status: Mapped[str] = mapped_column(default="active")


class AdCreativeLinkSlot(Base):
    """
    Модель слота ссылки в рекламном креативе.

    Используется для подмены ссылок и трекинга кликов.

    Атрибуты:
        id (int): Уникальный ID слота.
        creative_id (int): ID связанного креатива.
        slot_index (int): Индекс слота в сообщении.
        original_url (str): Оригинальная ссылка.
        location_type (str): Тип размещения (text/button).
        location_meta (dict): Метаданные размещения (позиция и т.д.).
        created_timestamp (int): Время создания.
    """
    __tablename__ = "ad_creative_link_slots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creative_id: Mapped[int] = mapped_column(index=True)
    slot_index: Mapped[int] = mapped_column()
    original_url: Mapped[str] = mapped_column()
    location_type: Mapped[str] = mapped_column()  # "text" или "button"
    location_meta: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
