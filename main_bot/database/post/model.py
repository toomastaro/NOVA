import time

from sqlalchemy import BigInteger, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Post(Base):
    __tablename__ = 'posts'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_ids: Mapped[list[int]] = mapped_column(ARRAY(BigInteger), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    message_options: Mapped[dict] = mapped_column(JSON, nullable=False)
    buttons: Mapped[str | None] = mapped_column()
    send_time: Mapped[int | None] = mapped_column(index=True, default=None)

    reaction: Mapped[dict | None] = mapped_column(JSON, default=None)
    hide: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON), default=None)

    pin_time: Mapped[int | None] = mapped_column(default=None)
    delete_time: Mapped[int | None] = mapped_column(default=None)
    report: Mapped[bool] = mapped_column(default=False)
    cpm_price: Mapped[int | None] = mapped_column(default=None)

    backup_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)

    created_timestamp: Mapped[int] = mapped_column(default=time.time)
