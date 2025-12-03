import time

from sqlalchemy import BigInteger, String, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class MtClient(Base):
    __tablename__ = 'mt_clients'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    pool_type: Mapped[str] = mapped_column(String(32), nullable=False)  # 'internal' or 'external'
    session_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default='NEW')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(BigInteger, default=lambda: int(time.time()))
    last_self_check_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    flood_wait_until: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
