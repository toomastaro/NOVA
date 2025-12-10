import time
from typing import Optional

from sqlalchemy import BigInteger
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class User(Base):
    """
    Модель пользователя Telegram бота (администратора каналов).
    """
    __tablename__ = 'users'

    # Основные данные
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='Telegram ID пользователя')
    balance: Mapped[float] = mapped_column(default=0, comment='Баланс пользователя')
    timezone: Mapped[int] = mapped_column(default=3, comment='Часовой пояс (UTC offset)')
    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()), comment='Дата регистрации')

    is_active: Mapped[bool] = mapped_column(default=True, comment='Активен ли пользователь')
    is_premium: Mapped[bool] = mapped_column(default=False, comment='Есть ли премиум')
    
    # Реферальная система
    referral_id: Mapped[Optional[int]] = mapped_column(BigInteger, default=None, comment='ID пригласившего пользователя')
    referral_earned: Mapped[int] = mapped_column(default=0, comment='Заработано на рефералах')
    ads_tag: Mapped[Optional[str]] = mapped_column(default=None, comment='Рекламная метка (откуда пришел)')

    default_exchange_rate_id: Mapped[int] = mapped_column(default=0, comment='Валюта по умолчанию (ID курса)')

    # Подписи к отчетам
    cpm_signature_active: Mapped[bool] = mapped_column(default=True, comment='Включена ли подпись CPM')
    cpm_signature_text: Mapped[Optional[str]] = mapped_column(default=None, comment='Текст подписи CPM')
    
    exchange_signature_active: Mapped[bool] = mapped_column(default=True, comment='Включена ли подпись курса')
    exchange_signature_text: Mapped[Optional[str]] = mapped_column(default=None, comment='Текст подписи курса')
    
    referral_signature_active: Mapped[bool] = mapped_column(default=True, comment='Включена ли реф. подпись')
    referral_signature_text: Mapped[Optional[str]] = mapped_column(default=None, comment='Текст реф. подписи')
