from main_bot.database import DatabaseMixin
from main_bot.database.promo.model import Promo
from sqlalchemy import delete, insert, select, update


class PromoCrud(DatabaseMixin):
    async def add_promo(self, **kwargs):
        await self.execute(insert(Promo).values(**kwargs))

    async def get_promo(self, name: str) -> Promo:
        return await self.fetchrow(select(Promo).where(Promo.name == name))

    async def use_promo(self, promo: Promo):
        if promo.use_count == 1:
            stmt = delete(Promo).where(Promo.name == promo.name)
        else:
            stmt = (
                update(Promo)
                .where(Promo.name == promo.name)
                .values(use_count=promo.use_count - 1)
            )

        await self.execute(stmt)
