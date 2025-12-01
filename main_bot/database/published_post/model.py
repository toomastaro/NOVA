import time

from sqlalchemy import BigInteger, JSON, ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class PublishedPost(Base):
    __tablename__ = 'published_posts'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(index=True)
    message_id: Mapped[int] = mapped_column(BigInteger, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    reaction: Mapped[dict | None] = mapped_column(JSON, default=None)
    hide: Mapped[list[dict] | None] = mapped_column(ARRAY(JSON), default=None)
    buttons: Mapped[str | None] = mapped_column()

    unpin_time: Mapped[int | None] = mapped_column(default=None)
    delete_time: Mapped[int | None] = mapped_column(default=None)
    report: Mapped[bool] = mapped_column(default=False)
    cpm_price: Mapped[int | None] = mapped_column(default=None)

    backup_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)

    created_timestamp: Mapped[int] = mapped_column(default=time.time)
