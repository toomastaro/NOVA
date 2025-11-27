from sqlalchemy import select, insert, update, func

from main_bot.database import DatabaseMixin
from main_bot.database.exchange_rate.model import ExchangeRate


class ExchangeRateCrud(DatabaseMixin):
    async def get_all_exchange_rate(self):
        return await self.fetch(
            select(ExchangeRate)
        )

    async def get_exchange_rate(self, exchange_rate_id: int) -> ExchangeRate:
        return await self.fetchrow(
            select(ExchangeRate).where(
                ExchangeRate.id == exchange_rate_id
            )
        )

    async def add_exchange_rate(self, **kwargs):
        await self.execute(
            insert(ExchangeRate).values(
                **kwargs
            )
        )

    async def update_exchange_rate(self, exchange_rate_id: int, return_obj: bool = False, **kwargs) -> ExchangeRate | None:
        stmt = update(ExchangeRate).where(ExchangeRate.id == exchange_rate_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(ExchangeRate)
        else:
            operation = self.execute
        return await operation(stmt, **{'commit': return_obj} if return_obj else {})
