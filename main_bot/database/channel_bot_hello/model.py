from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ChannelHelloMessage(Base):
    __tablename__ = 'channel_hello_messages'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    delay: Mapped[int] = mapped_column(default=0)
    text_with_name: Mapped[bool] = mapped_column(default=False)
    is_active: Mapped[bool] = mapped_column(default=True)
