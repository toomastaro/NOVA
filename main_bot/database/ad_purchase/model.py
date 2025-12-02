import time
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column
from main_bot.database import Base
from main_bot.database.types import AdPricingType, AdTargetType


class AdPurchase(Base):
    __tablename__ = "ad_purchases"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(BigInteger, index=True)
    creative_id: Mapped[int] = mapped_column(index=True)
    pricing_type: Mapped[AdPricingType] = mapped_column()
    price_value: Mapped[int] = mapped_column()
    comment: Mapped[str | None] = mapped_column(default=None)
    status: Mapped[str] = mapped_column(default="active")
    created_timestamp: Mapped[int] = mapped_column(default=time.time)


class AdPurchaseLinkMapping(Base):
    __tablename__ = "ad_purchase_link_mappings"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ad_purchase_id: Mapped[int] = mapped_column(index=True)
    slot_id: Mapped[int] = mapped_column(index=True)
    original_url: Mapped[str] = mapped_column()
    target_type: Mapped[AdTargetType] = mapped_column()
    target_channel_id: Mapped[int | None] = mapped_column(BigInteger, default=None)
    invite_link: Mapped[str | None] = mapped_column(default=None)
    ref_param: Mapped[str | None] = mapped_column(default=None)
    track_enabled: Mapped[bool] = mapped_column(default=True)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
