from sqlalchemy import BigInteger, String, Integer, ForeignKey, Column
from sqlalchemy.orm import Mapped, mapped_column, relationship
from main_bot.database import Base

class NovaStatSettings(Base):
    __tablename__ = 'novastat_settings'

    user_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    depth_days: Mapped[int] = mapped_column(Integer, default=7)

class Collection(Base):
    __tablename__ = 'novastat_collections'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    channels = relationship("CollectionChannel", back_populates="collection", cascade="all, delete-orphan")

class CollectionChannel(Base):
    __tablename__ = 'novastat_collection_channels'

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey('novastat_collections.id'), nullable=False)
    channel_identifier: Mapped[str] = mapped_column(String, nullable=False) # username or link
    
    collection = relationship("Collection", back_populates="channels")
