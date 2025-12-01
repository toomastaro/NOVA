import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class User(Base):
    __tablename__ = 'users'

    # Data
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    balance: Mapped[float] = mapped_column(default=0)
    timezone: Mapped[int] = mapped_column(default=3)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)

    is_active: Mapped[bool] = mapped_column(default=True)
    is_premium: Mapped[bool] = mapped_column(default=False)
    referral_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    referral_earned: Mapped[int] = mapped_column(default=0)
    ads_tag: Mapped[str | None] = mapped_column(default=None)
