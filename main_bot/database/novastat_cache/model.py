import time
from typing import Optional

from sqlalchemy import BigInteger, String, Boolean, JSON, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class NovaStatCache(Base):
    """
    Кэш статистики каналов для NovaStat.
    Хранит вычисленные значения просмотров и ER для разных горизонтов (24/48/72 часа).
    """
    __tablename__ = 'novastat_channel_cache'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    channel_identifier: Mapped[str] = mapped_column(String(255), nullable=False)  # username или ссылка
    horizon: Mapped[int] = mapped_column(nullable=False)  # 24, 48 или 72
    value_json: Mapped[dict] = mapped_column(JSON, nullable=False)  # вычисленные значения
    updated_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    refresh_in_progress: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    __table_args__ = (
        UniqueConstraint('channel_identifier', 'horizon', name='uq_channel_horizon'),
    )
