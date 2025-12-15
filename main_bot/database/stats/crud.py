from main_bot.database import DatabaseMixin
from main_bot.database.stats.model import Stats
from sqlalchemy import insert


class StatsCrud(DatabaseMixin):
    async def update_stats(self, **kwargs):
        await self.execute(insert(Stats).values(**kwargs))
