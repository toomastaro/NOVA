"""
Модель данных курса валют.
"""

from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ExchangeRate(Base):
    """
    Модель курса валют.

    Атрибуты:
        id (int): Уникальный ID.
        name (str): Название валюты (например, USD).
        rate (float): Текущий курс.
        last_update (datetime): Время последнего обновления.
    """

    __tablename__ = "exchange_rate"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    rate: Mapped[float] = mapped_column()
    last_update: Mapped[datetime] = mapped_column(DateTime)
