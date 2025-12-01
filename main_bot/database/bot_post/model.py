import time

from sqlalchemy import BigInteger, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.types import Status


class BotPost(Base):
    __tablename__ = 'bot_posts'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    chat_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    message: Mapped[dict] = mapped_column(JSON, nullable=False)
    send_time: Mapped[int | None] = mapped_column(index=True, default=None)
    delete_time: Mapped[int | None] = mapped_column(default=None)

    report: Mapped[bool] = mapped_column(default=False)
    text_with_name: Mapped[bool] = mapped_column(default=False)

    created_timestamp: Mapped[int] = mapped_column(default=time.time)

    # Report Data
    status: Mapped[Status] = mapped_column(default=Status.PENDING)
    start_timestamp: Mapped[int | None] = mapped_column(default=None)
    end_timestamp: Mapped[int | None] = mapped_column(default=None)
    success_send: Mapped[int] = mapped_column(default=0)
    error_send: Mapped[int] = mapped_column(default=0)
    message_ids: Mapped[dict | None] = mapped_column(JSON, default=None)
