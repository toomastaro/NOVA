import time
import uuid

from main_bot.database import Base
from sqlalchemy import JSON, BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column


class PaymentLink(Base):
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
