"""
Модель данных для рекламных тегов.
"""

from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class AdTag(Base):
    """
    Модель рекламного тега.

    Используется для маркировки и отслеживания кликов.

    Атрибуты:
        name (str): Название тега (PK).
        title (str): Заголовок/описание.
        click_count (int): Общее количество кликов.
        unic_click_count (int): Количество уникальных кликов.
    """
    __tablename__ = "ad_tags"

    # Данные
    name: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    click_count: Mapped[int] = mapped_column(default=0)
    unic_click_count: Mapped[int] = mapped_column(default=0)
