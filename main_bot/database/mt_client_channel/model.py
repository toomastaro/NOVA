"""
Модель данных связи клиента с каналом (членство).
"""

from sqlalchemy import BigInteger, Boolean, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from main_bot.database import Base
from main_bot.database.mt_client.model import MtClient


class MtClientChannel(Base):
    """
    Связь MtClient (юзербота) и Channel (канала).

    Описывает статус пользователя (клиента) в конкретном канале:
    является ли участником, админом, может ли постить истории и т.д.

    Атрибуты:
        id (int): Уникальный ID связи.
        client_id (int): ID клиента (MtClient).
        channel_id (int): ID канала (Channel).
        is_member (bool): Является ли участником/подписчиком.
        is_admin (bool): Является ли администратором.
        can_post_stories (bool): Есть ли право публиковать истории.
        preferred_for_stats (bool): Предпочтительный клиент для сбора статистики.
        preferred_for_stories (bool): Предпочтительный клиент для постинга историй.
        last_joined_at (int | None): Когда вступил в канал.
        last_seen_at (int | None): Когда последний раз проверялся статус.
        last_error_code (str | None): Последняя ошибка при взаимодействии.
        last_error_at (int | None): Время последней ошибки.
    """

    __tablename__ = "mt_client_channels"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)

    client = relationship(
        MtClient,
        primaryjoin=client_id == MtClient.id,
        foreign_keys=[client_id],
        lazy="joined",
    )

    is_member: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    can_post_messages: Mapped[bool] = mapped_column(Boolean, default=False)
    can_post_stories: Mapped[bool] = mapped_column(Boolean, default=False)

    preferred_for_stats: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_for_stories: Mapped[bool] = mapped_column(Boolean, default=False)

    last_joined_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_seen_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint("client_id", "channel_id", name="uq_client_channel"),
        Index("idx_channel_stats", "channel_id", "preferred_for_stats"),
        Index("idx_channel_stories", "channel_id", "preferred_for_stories"),
    )
