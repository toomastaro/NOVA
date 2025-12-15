from main_bot.database import Base
from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column


class ChannelCaptcha(Base):
    __tablename__ = "channel_captcha"

    # Data
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    delay: Mapped[int] = mapped_column(default=0)
