from sqlalchemy import BigInteger, Boolean, String, UniqueConstraint, Index, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from main_bot.database import Base


class MtClientChannel(Base):
    __tablename__ = 'mt_client_channels'

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    client_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("mt_clients.id"), nullable=False)
    channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    
    client = relationship("MtClient", lazy="joined")
    
    is_member: Mapped[bool] = mapped_column(Boolean, default=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    can_post_stories: Mapped[bool] = mapped_column(Boolean, default=False)
    
    preferred_for_stats: Mapped[bool] = mapped_column(Boolean, default=False)
    preferred_for_stories: Mapped[bool] = mapped_column(Boolean, default=False)
    
    last_joined_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    last_seen_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    
    last_error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    last_error_at: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    __table_args__ = (
        UniqueConstraint('client_id', 'channel_id', name='uq_client_channel'),
        Index('idx_channel_stats', 'channel_id', 'preferred_for_stats'),
        Index('idx_channel_stories', 'channel_id', 'preferred_for_stories'),
    )
