import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.types import PaymentMethod


class Payment(Base):
    __tablename__ = 'payments'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, default=10)
    amount: Mapped[int] = mapped_column()
    method: Mapped[PaymentMethod] = mapped_column()
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
