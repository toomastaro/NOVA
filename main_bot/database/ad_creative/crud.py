import logging


from main_bot.database import DatabaseMixin
from main_bot.database.ad_creative.model import AdCreative, AdCreativeLinkSlot
from sqlalchemy import insert, select, update

logger = logging.getLogger(__name__)


class AdCreativeCrud(DatabaseMixin):
    async def create_creative(self, **kwargs) -> int:
        """Создает новый рекламный креатив."""
        query = insert(AdCreative).values(**kwargs).returning(AdCreative.id)
        return await self.fetchrow(query, commit=True)

    async def get_creative(self, creative_id: int) -> AdCreative | None:
        """Получает рекламный креатив по ID."""
        query = select(AdCreative).where(AdCreative.id == creative_id)
        return await self.fetchrow(query)

    async def get_user_creatives(self, owner_id: int) -> list[AdCreative]:
        """Получает список рекламных креативов, принадлежащих пользователю."""
        query = select(AdCreative).where(
            AdCreative.owner_id == owner_id, AdCreative.status != "deleted"
        )
        return await self.fetch(query)

    async def create_slots_for_creative(
        self, creative_id: int, slots: list[dict]
    ) -> None:
        """Создает слоты ссылок для креатива."""
        if not slots:
            return
        values = [{**slot, "creative_id": creative_id} for slot in slots]
        query = insert(AdCreativeLinkSlot).values(values)
        await self.execute(query)

    async def get_slots(self, creative_id: int) -> list[AdCreativeLinkSlot]:
        """Получает список слотов для креатива."""
        query = select(AdCreativeLinkSlot).where(
            AdCreativeLinkSlot.creative_id == creative_id
        )
        return await self.fetch(query)

    async def update_creative_status(self, creative_id: int, status: str) -> None:
        """Обновляет статус креатива."""

        query = (
            update(AdCreative).where(AdCreative.id == creative_id).values(status=status)
        )
        await self.execute(query)
