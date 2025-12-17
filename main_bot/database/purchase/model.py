"""
Модель данных покупки (история операций).
"""

import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import PaymentMethod, Service


class Purchase(Base):
    """
    Модель покупки. Хранит историю трат пользователя.

    Атрибуты:
        id (int): Уникальный ID записи.
        user_id (int): ID пользователя.
        amount (int): Сумма покупки.
        method (PaymentMethod): Способ оплаты (BALANCE, STARS и т.д.).
        service (Service): Услуга (POSTING, BOTS и т.д.).
        created_timestamp (int): Время покупки.
    """

    __tablename__ = "purchases"

    # Данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, default=10)
    amount: Mapped[int] = mapped_column()
    method: Mapped[PaymentMethod] = mapped_column()
    service: Mapped[Service] = mapped_column()
    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()))
