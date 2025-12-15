import time

from main_bot.database import Base
from main_bot.database.db_types import AdPricingType, AdTargetType
from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column


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
    last_scanned_id: Mapped[int] = mapped_column(BigInteger, default=0)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)


class AdLead(Base):
    __tablename__ = "ad_leads"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_purchase_id: Mapped[int] = mapped_column(index=True)
    slot_id: Mapped[int] = mapped_column()
    ref_param: Mapped[str] = mapped_column()
    created_timestamp: Mapped[int] = mapped_column(default=time.time)


class AdSubscription(Base):
    __tablename__ = "ad_subscriptions"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    channel_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_purchase_id: Mapped[int] = mapped_column(index=True)
    slot_id: Mapped[int] = mapped_column()
    invite_link: Mapped[str] = mapped_column()
    status: Mapped[str] = mapped_column(default="active")  # 'active', 'left', 'kicked'
    left_timestamp: Mapped[int | None] = mapped_column(default=None)
    created_timestamp: Mapped[int] = mapped_column(default=time.time)
