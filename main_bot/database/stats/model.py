"""
Модель данных глобальной статистики.
"""

from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Stats(Base):
    """
    Модель глобальной статистики (счетчики ботов, каналов).

    Атрибуты:
        id (int): Уникальный ID записи.
        bot_count (int): Количество ботов.
        channel_count (int): Количество каналов.
    """
    __tablename__ = "stats"

    # Данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    bot_count: Mapped[int] = mapped_column(default=0)
    channel_count: Mapped[int] = mapped_column(default=0)
