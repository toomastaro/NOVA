from sqlalchemy.orm import Mapped, mapped_column

from main_bot.database import Base


class Promo(Base):
    __tablename__ = 'promo'

    # Data
    name: Mapped[str] = mapped_column(primary_key=True)
    use_count: Mapped[int] = mapped_column(default=10)
    amount: Mapped[int | None] = mapped_column()
    discount: Mapped[int | None] = mapped_column()
