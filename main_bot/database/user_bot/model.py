import time
from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class UserBot(Base):
    """
    Модель UserBot (юзербота, подключенного пользователем).
    """
    __tablename__ = 'user_bots'

    # Основные данные
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, comment='Внутренний ID бота')
    admin_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='ID владельца (User)')
    schema: Mapped[str] = mapped_column(String, nullable=False, comment='Схема/протокол (напр. MTProto)')

    title: Mapped[str] = mapped_column(nullable=False, comment='Название/Имя бота')
    username: Mapped[str] = mapped_column(unique=True, nullable=False, comment='Username бота')
    token: Mapped[str] = mapped_column(String(256), nullable=False, comment='Токен авторизации')
    
    subscribe: Mapped[Optional[int]] = mapped_column(default=None, comment='Время окончания подписки')
    emoji_id: Mapped[str] = mapped_column(nullable=False, comment='Emoji ID')

    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()), comment='Дата создания')
