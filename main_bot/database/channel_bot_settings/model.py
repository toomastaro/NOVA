from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ChannelBotSetting(Base):
    __tablename__ = 'channels_bot_settings'

    # Data
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, default=None)

    # Settings
    auto_approve: Mapped[bool] = mapped_column(default=False)
    delay_approve: Mapped[int] = mapped_column(default=0)
    bye: Mapped[dict | None] = mapped_column(JSON)
    active_captcha_id: Mapped[int | None] = mapped_column(default=None)
