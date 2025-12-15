from main_bot.database import Base
from sqlalchemy.orm import Mapped, mapped_column


class AdTag(Base):
    __tablename__ = "ad_tags"

    # Data
    name: Mapped[str] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column()
    click_count: Mapped[int] = mapped_column(default=0)
    unic_click_count: Mapped[int] = mapped_column(default=0)
