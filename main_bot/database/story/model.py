import time

from sqlalchemy import BigInteger, JSON
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.types import Status


class Story(Base):
    __tablename__ = 'stories'

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    chat_ids: Mapped[list] = mapped_column(ARRAY(BigInteger), index=True)
    admin_id: Mapped[int] = mapped_column(BigInteger, index=True)

    story_options: Mapped[dict] = mapped_column(JSON, nullable=False)
    send_time: Mapped[int | None] = mapped_column(index=True)

    report: Mapped[bool] = mapped_column(default=False)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)

    # Backup & Status
    backup_chat_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    backup_message_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    status: Mapped[Status] = mapped_column(default=Status.PENDING)
    delete_time: Mapped[int | None] = mapped_column(default=None)
