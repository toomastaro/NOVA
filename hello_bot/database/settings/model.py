from sqlalchemy import JSON, BigInteger
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from hello_bot.database import Base


class Setting(Base):
    """Модель настроек hello_bot."""

    __tablename__ = "settings"

    # Data
    id: Mapped[int] = mapped_column(autoincrement=True, primary_key=True)
    hello: Mapped[dict | None] = mapped_column(JSON)
    bye: Mapped[dict | None] = mapped_column(JSON)
    answers: Mapped[list[dict]] = mapped_column(ARRAY(JSON), default=[])
    protect: Mapped[dict | None] = mapped_column(JSON, default=None)
    auto_approve: Mapped[int] = mapped_column(default=0)
    delay_approve: Mapped[int] = mapped_column(default=0)
    input_messages: Mapped[int] = mapped_column(default=0)
    output_messages: Mapped[int] = mapped_column(default=0)
    channel_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    channel_title: Mapped[str | None] = mapped_column(default=None)
    channel_emoji_id: Mapped[str | None] = mapped_column(default=None)
