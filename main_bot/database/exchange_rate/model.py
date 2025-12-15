from datetime import datetime

from main_bot.database import Base
from sqlalchemy import DateTime
from sqlalchemy.orm import Mapped, mapped_column


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column()
    rate: Mapped[float] = mapped_column()
    last_update: Mapped[datetime] = mapped_column(DateTime)
