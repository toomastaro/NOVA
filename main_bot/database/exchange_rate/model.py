import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import DateTime
from main_bot.database import Base
from datetime import datetime


class ExchangeRate(Base):
    __tablename__ = 'exchange_rate'

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    rate: Mapped[float] = mapped_column()
    last_update: Mapped[datetime] = mapped_column(DateTime)
