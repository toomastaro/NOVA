from sqlalchemy import insert, select

from main_bot.database import DatabaseMixin
from main_bot.database.purchase.model import Purchase


class PurchaseCrud(DatabaseMixin):
    async def add_purchase(self, **kwargs):
        await self.execute(
            insert(Purchase).values(
                **kwargs
            )
        )

    async def has_purchase(self, user_id: int) -> Purchase:
        return await self.fetchrow(
            select(Purchase).where(
                Purchase.user_id == user_id
            ).limit(1)
        )
