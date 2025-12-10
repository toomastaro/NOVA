import time
from typing import Optional

from sqlalchemy import BigInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Channel(Base):
    """
    Модель Telegram-канала.
    """
    __tablename__ = 'channels'

    # Основные данные
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True, comment='Внутренний ID канала')
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, comment='Telegram ID канала')
    title: Mapped[str] = mapped_column(String(64), nullable=False, comment='Название канала')
    admin_id: Mapped[int] = mapped_column(BigInteger, comment='ID владельца (админа)')
    
    subscribe: Mapped[Optional[int]] = mapped_column(comment='Время окончания подписки (timestamp)')
    session_path: Mapped[Optional[str]] = mapped_column(comment='Путь к сессии (для юзерботов)')
    emoji_id: Mapped[str] = mapped_column(nullable=False, comment='ID эмодзи для капчи/оформления')
    created_timestamp: Mapped[int] = mapped_column(default=lambda: int(time.time()), comment='Дата добавления')
    
    # Распределение нагрузки (Round-robin)
    last_client_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, default=None, comment='ID последнего использованного клиента')
