from main_bot.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class Stats(Base):
    __tablename__ = "stats"

    # Data
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_count: Mapped[int] = mapped_column(default=0)
    channel_count: Mapped[int] = mapped_column(default=0)
