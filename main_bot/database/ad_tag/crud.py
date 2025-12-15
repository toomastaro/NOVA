import logging


from main_bot.database import DatabaseMixin
from main_bot.database.ad_tag.model import AdTag
from sqlalchemy import delete, insert, select, update

logger = logging.getLogger(__name__)


class AdTagCrud(DatabaseMixin):
    async def add_ad_tag(self, **kwargs):
        """Создает новый рекламный тег."""
        await self.execute(insert(AdTag).values(**kwargs))

    async def remove_ad_tag(self, name: str):
        """Удаляет тег по имени."""
        await self.execute(delete(AdTag).where(AdTag.name == name))

    async def get_ad_tag(self, name: str) -> AdTag:
        """Получает тег по имени."""
        return await self.fetchrow(select(AdTag).where(AdTag.name == name))

    async def update_ad_tag(self, name: str, **kwargs):
        await self.execute(update(AdTag).where(AdTag.name == name).values(**kwargs))
