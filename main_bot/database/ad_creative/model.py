import time

from main_bot.database import Base
from sqlalchemy import JSON, BigInteger
from sqlalchemy.orm import Mapped, mapped_column


class AdCreative(Base):
    __tablename__ = "ad_creatives"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    name: Mapped[str] = mapped_column()
    raw_message: Mapped[dict] = mapped_column(JSON)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
    status: Mapped[str] = mapped_column(default="active")


class AdCreativeLinkSlot(Base):
    __tablename__ = "ad_creative_link_slots"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    creative_id: Mapped[int] = mapped_column(index=True)
    slot_index: Mapped[int] = mapped_column()
    original_url: Mapped[str] = mapped_column()
    location_type: Mapped[str] = mapped_column()  # "text" или "button"
    location_meta: Mapped[dict | None] = mapped_column(JSON, default=None)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
