"""
Модель данных ссылки на оплату (для внешних платежных систем).
"""

import time
import uuid

from sqlalchemy import JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class PaymentLink(Base):
    """
    Модель ссылки на оплату.

    Используется для создания временных ссылок или инвойсов для платежных систем (например, Platega).

    Атрибуты:
        id (str): Уникальный ID платежа (UUID).
        user_id (int): ID пользователя.
        amount (int): Сумма.
        currency (str): Валюта (по умолчанию RUB).
        status (str): Статус платежа (PENDING, PAID, CANCELED).
        payload (dict): Контекстные данные (тип услуги, параметры).
        created_timestamp (int): Время создания.
    """
    __tablename__ = "payment_links"

    # PK is a String (UUID) to match Platega order_id requirement easily
    id: Mapped[str] = mapped_column(
        String, primary_key=True, default=lambda: str(uuid.uuid4())
    )

    user_id: Mapped[int] = mapped_column(BigInteger)
    amount: Mapped[int] = mapped_column()
    currency: Mapped[str] = mapped_column(String, default="RUB")

    # Status: PENDING, PAID, CANCELED
    status: Mapped[str] = mapped_column(String, default="PENDING")

    # Context payload: e.g. {"type": "balance"} or {"type": "sub", "days": 30, ...}
    payload: Mapped[dict] = mapped_column(JSON, default={})

    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()))
