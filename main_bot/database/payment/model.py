"""
Модель данных платежа для пополнения баланса.
"""

import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import PaymentMethod


class Payment(Base):
    """
    Модель платежа (пополнение баланса пользователя).

    Атрибуты:
        id (int): Уникальный ID платежа.
        user_id (int): ID пользователя (Telegram ID).
        amount (int): Сумма пополнения.
        method (PaymentMethod): Метод оплаты.
        created_timestamp (int): Время создания.
    """
    __tablename__ = "payments"

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, default=10)
    amount: Mapped[int] = mapped_column()
    method: Mapped[PaymentMethod] = mapped_column()
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
