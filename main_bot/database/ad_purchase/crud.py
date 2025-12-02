from sqlalchemy import select, insert, update
from main_bot.database import DatabaseMixin
from main_bot.database.ad_purchase.model import AdPurchase, AdPurchaseLinkMapping


class AdPurchaseCrud(DatabaseMixin):
    async def create_purchase(self, **kwargs) -> int:
        query = insert(AdPurchase).values(**kwargs).returning(AdPurchase.id)
        return await self.fetchrow(query, commit=True)

    async def get_purchase(self, purchase_id: int) -> AdPurchase | None:
        query = select(AdPurchase).where(AdPurchase.id == purchase_id)
        return await self.fetchrow(query)

    async def get_user_purchases(self, owner_id: int) -> list[AdPurchase]:
        query = select(AdPurchase).where(AdPurchase.owner_id == owner_id)
        return await self.fetch(query)

    async def upsert_link_mapping(self, ad_purchase_id: int, slot_id: int, **kwargs) -> None:
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.ad_purchase_id == ad_purchase_id,
            AdPurchaseLinkMapping.slot_id == slot_id
        )
        existing = await self.fetchrow(query)

        if existing:
            query = update(AdPurchaseLinkMapping).where(
                AdPurchaseLinkMapping.id == existing.id
            ).values(**kwargs)
        else:
            query = insert(AdPurchaseLinkMapping).values(
                ad_purchase_id=ad_purchase_id,
                slot_id=slot_id,
                **kwargs
            )
        await self.execute(query)

    async def get_link_mappings(self, ad_purchase_id: int) -> list[AdPurchaseLinkMapping]:
        query = select(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.ad_purchase_id == ad_purchase_id)
        return await self.fetch(query)

    async def update_purchase_status(self, purchase_id: int, status: str) -> None:
        query = update(AdPurchase).where(AdPurchase.id == purchase_id).values(status=status)
        await self.execute(query)

