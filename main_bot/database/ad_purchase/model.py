"""
Модели данных для рекламных закупок и трекинга.

Описывает таблицы:
- AdPurchase: Рекламная закупка.
- AdPurchaseLinkMapping: Привязка ссылок для отслеживания.
- AdLead: Лид (пользователь, перешедший по ссылке).
- AdSubscription: Подписка пользователя на канал/бота.
"""

import time

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base
from main_bot.database.db_types import AdPricingType, AdTargetType


class AdPurchase(Base):
    """
    Модель рекламной закупки.

    Атрибуты:
        id (int): Уникальный ID закупки.
        owner_id (int): ID владельца (рекламодателя).
        creative_id (int): ID рекламного креатива.
        pricing_type (AdPricingType): Тип оплаты (CPL, CPS, Fixed).
        price_value (int): Стоимость (за действие или фиксированная).
        comment (str): Комментарий пользователя.
        status (str): Статус закупки (active, deleted).
        created_timestamp (int): Время создания.
    """

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
    """
    Модель маппинга ссылок в креативе к конкретной закупке.

    Используется для создания уникальных пригласительных ссылок
    для каждого слота в креативе при публикации.

    Атрибуты:
        id (int): ID записи.
        ad_purchase_id (int): ID закупки.
        slot_id (int): ID слота ссылки в креативе.
        original_url (str): Исходная ссылка (для редиректа или fallback).
        target_type (AdTargetType): Тип цели (канал, бот, внешняя).
        target_channel_id (int): ID целевого канала (если есть).
        invite_link (str): Сгенерированная пригласительная ссылка (Telegram).
        ref_param (str): Реферальный параметр (для ботов).
        track_enabled (bool): Включено ли отслеживание.
        last_scanned_id (int): ID последнего сканированного события (для JoinRequest).
        created_timestamp (int): Время создания.
    """

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
    """
    Модель лида (переход по ссылке).

    Фиксирует факт перехода пользователя по рекламной ссылке.

    Атрибуты:
        id (int): ID события.
        user_id (int): ID пользователя.
        ad_purchase_id (int): ID закупки.
        slot_id (int): ID слота ссылки.
        ref_param (str): Использованный реф. параметр.
        created_timestamp (int): Время перехода.
    """

    __tablename__ = "ad_leads"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    ad_purchase_id: Mapped[int] = mapped_column(index=True)
    slot_id: Mapped[int] = mapped_column()
    ref_param: Mapped[str] = mapped_column()
    created_timestamp: Mapped[int] = mapped_column(default=time.time)


class AdSubscription(Base):
    """
    Модель подписки, полученной через рекламу.

    Фиксирует факт вступления пользователя в канал/бота по рекламной ссылке.

    Атрибуты:
        id (int): ID подписки.
        user_id (int): ID пользователя.
        channel_id (int): ID канала/бота.
        ad_purchase_id (int): ID закупки.
        slot_id (int): ID слота.
        invite_link (str): Ссылка, по которой пришел юзер.
        status (str): Статус подписки (active, left и т.д.).
        left_timestamp (int): Время отписки.
        created_timestamp (int): Время подписки.
    """

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
