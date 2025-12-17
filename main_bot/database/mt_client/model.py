"""
Модель данных MTProto клиента.
"""

import time

from sqlalchemy import BigInteger, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class MtClient(Base):
    """
    Модель MTProto клиента (юзербота).

    Используется для взаимодействия с Telegram от имени пользователя или системного аккаунта.

    Атрибуты:
        id (int): Уникальный ID.
        alias (str): Псевдоним клиента.
        pool_type (str): Тип пула ('internal' или 'external').
        session_path (str): Путь к файлу сессии.
        status (str): Статус клиента (NEW, ACTIVE, BANNED, ERROR).
        is_active (bool): Флаг активности (включен/выключен).
        created_at (int): Время создания.
        last_self_check_at (int | None): Время последней самопроверки.
        last_error_code (str | None): Код последней ошибки.
        last_error_at (int | None): Время последней ошибки.
        flood_wait_until (int | None): Метка времени до окончания FloodWait.
        usage_count (int): Счетчик использований.
        last_used_at (int): Время последнего использования.
    """
    __tablename__ = "mt_clients"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alias: Mapped[str] = mapped_column(String(64), nullable=False)
    pool_type: Mapped[str] = mapped_column(
        String(32), nullable=False
    )  # 'internal' or 'external'
    session_path: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEW")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[int] = mapped_column(
        BigInteger, default=lambda: int(time.time())
    )
    last_self_check_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    flood_wait_until: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Round-robin distribution fields
    usage_count: Mapped[int] = mapped_column(BigInteger, default=0)
    last_used_at: Mapped[int] = mapped_column(BigInteger, default=0)
