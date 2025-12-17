"""
Модель данных настроек бота для конкретного канала.
"""

from sqlalchemy import BigInteger
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class ChannelBotSetting(Base):
    """
    Модель настроек бота для канала (автоприем заявок, прощание и т.д.).

    Атрибуты:
        id (int): Уникальный ID (совпадает с chat_id канала).
        admin_id (int): ID администратора.
        bot_id (int | None): ID подключенного бота.
        auto_approve (bool): Автоприем заявок на вступление.
        delay_approve (int): Задержка автоприема (в секундах).
        bye (dict | None): Конфигурация прощальных сообщений.
        active_captcha_id (int | None): ID активной капчи.
    """

    __tablename__ = "channels_bot_settings"

    # Данные
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)  # chat_id
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    bot_id: Mapped[int | None] = mapped_column(BigInteger, default=None)

    # Настройки
    auto_approve: Mapped[bool] = mapped_column(default=False)
    delay_approve: Mapped[int] = mapped_column(default=0)
    bye: Mapped[dict | None] = mapped_column(JSON)
    active_captcha_id: Mapped[int | None] = mapped_column(default=None)
