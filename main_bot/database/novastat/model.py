"""
Модели данных для модуля статистики NovaStat.
"""

from sqlalchemy import BigInteger, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from main_bot.database import Base


class NovaStatSettings(Base):
    """
    Модель настроек статистики для пользователя.

    Атрибуты:
        user_id (int): ID пользователя (Telegram ID).
        depth_days (int): Глубина анализа в днях.
    """

    __tablename__ = "novastat_settings"

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    depth_days: Mapped[int] = mapped_column(Integer, default=7)


class Collection(Base):
    """
    Модель коллекции каналов для статистики.

    Атрибуты:
        id (int): Уникальный ID коллекции.
        user_id (int): ID владельца.
        name (str): Название коллекции.
        channels (list[CollectionChannel]): Связанные каналы.
    """

    __tablename__ = "novastat_collections"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    channels = relationship(
        "CollectionChannel", back_populates="collection", cascade="all, delete-orphan"
    )


class CollectionChannel(Base):
    """
    Модель канала в коллекции статистики.

    Атрибуты:
        id (int): Уникальный ID записи.
        collection_id (int): ID коллекции.
        channel_identifier (str): Идентификатор канала (username/link).
    """

    __tablename__ = "novastat_collection_channels"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(
        ForeignKey("novastat_collections.id"), nullable=False
    )
    channel_identifier: Mapped[str] = mapped_column(
        String, nullable=False
    )  # username или ссылка

    collection = relationship("Collection", back_populates="channels")
