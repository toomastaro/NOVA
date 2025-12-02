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
        query = select(AdPurchase).where(
            AdPurchase.owner_id == owner_id,
            AdPurchase.status != "deleted"
        )
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

    async def ensure_invite_links(self, ad_purchase_id: int, bot) -> list[AdPurchaseLinkMapping]:
        from main_bot.database.types import AdTargetType
        
        mappings = await self.get_link_mappings(ad_purchase_id)
        updated_mappings = []
        
        for m in mappings:
            if m.target_type == AdTargetType.CHANNEL and m.track_enabled and m.target_channel_id and not m.invite_link:
                try:
                    # Create invite link
                    invite = await bot.create_chat_invite_link(
                        chat_id=m.target_channel_id,
                        name=f"AdPurchase #{ad_purchase_id}"
                    )
                    
                    # Update DB
                    query = update(AdPurchaseLinkMapping).where(
                        AdPurchaseLinkMapping.id == m.id
                    ).values(invite_link=invite.invite_link)
                    await self.execute(query)
                    
                    # Update local object
                    m.invite_link = invite.invite_link
                except Exception as e:
                    # Log error but continue
                    print(f"Error creating invite link for purchase {ad_purchase_id}, slot {m.slot_id}: {e}")
            
            updated_mappings.append(m)
            
        return updated_mappings

