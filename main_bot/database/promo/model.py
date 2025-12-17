"""
Модель данных промокода.
"""

from typing import Optional

from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Promo(Base):
    """
    Модель промокода.

    Атрибуты:
        name (str): Код промокода (PK).
        use_count (int): Оставшееся количество использований.
        amount (int | None): Фиксированная сумма бонуса/скидки.
        discount (int | None): Процент скидки.
    """
    __tablename__ = "promo"

    # Данные
    name: Mapped[str] = mapped_column(primary_key=True)
    use_count: Mapped[int] = mapped_column(default=10)
    amount: Mapped[Optional[int]] = mapped_column()
    discount: Mapped[Optional[int]] = mapped_column()
