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

    async def ensure_invite_links(self, ad_purchase_id: int, bot) -> tuple[list[AdPurchaseLinkMapping], list[str]]:
        """
        Ensure invite links are created for all channel mappings.
        Returns: (mappings, errors) - list of mappings and list of error messages
        """
        from main_bot.database.types import AdTargetType
        import logging
        
        logger = logging.getLogger(__name__)
        mappings = await self.get_link_mappings(ad_purchase_id)
        updated_mappings = []
        errors = []
        
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
                    logger.info(f"Created invite link for purchase {ad_purchase_id}, slot {m.slot_id}, channel {m.target_channel_id}: {invite.invite_link}")
                except Exception as e:
                    error_msg = f"Ошибка создания ссылки для канала {m.target_channel_id}: {str(e)}"
                    logger.error(f"Error creating invite link for purchase {ad_purchase_id}, slot {m.slot_id}: {e}")
                    errors.append(error_msg)
            
            updated_mappings.append(m)
            
        return updated_mappings, errors

    async def add_lead(self, user_id: int, ad_purchase_id: int, slot_id: int, ref_param: str) -> bool:
        """
        Add a lead for an ad purchase. Returns True if lead was created, False if already exists.
        """
        from main_bot.database.ad_purchase.model import AdLead
        
        # Check if lead already exists
        query = select(AdLead).where(
            AdLead.user_id == user_id,
            AdLead.ad_purchase_id == ad_purchase_id
        )
        existing = await self.fetchrow(query)
        
        if existing:
            return False
        
        # Create new lead
        query = insert(AdLead).values(
            user_id=user_id,
            ad_purchase_id=ad_purchase_id,
            slot_id=slot_id,
            ref_param=ref_param
        )
        await self.execute(query)
        return True

    async def get_leads_count(self, ad_purchase_id: int) -> int:
        """Get total number of leads for an ad purchase."""
        from main_bot.database.ad_purchase.model import AdLead
        from sqlalchemy import func
        
        query = select(func.count(AdLead.id)).where(AdLead.ad_purchase_id == ad_purchase_id)
        result = await self.fetchrow(query)
        return result if result else 0

    async def get_leads_by_slot(self, ad_purchase_id: int, slot_id: int) -> list:
        """Get all leads for a specific slot."""
        from main_bot.database.ad_purchase.model import AdLead
        
        query = select(AdLead).where(
            AdLead.ad_purchase_id == ad_purchase_id,
            AdLead.slot_id == slot_id
        )
        return await self.fetch(query)


    async def add_subscription(self, user_id: int, channel_id: int, ad_purchase_id: int, slot_id: int, invite_link: str) -> bool:
        """
        Add a subscription for an ad purchase. Returns True if subscription was created, False if already exists.
        """
        from main_bot.database.ad_purchase.model import AdSubscription
        
        # Check if subscription already exists
        query = select(AdSubscription).where(
            AdSubscription.user_id == user_id,
            AdSubscription.channel_id == channel_id,
            AdSubscription.ad_purchase_id == ad_purchase_id
        )
        existing = await self.fetchrow(query)
        
        if existing:
            return False
        
        # Create new subscription
        query = insert(AdSubscription).values(
            user_id=user_id,
            channel_id=channel_id,
            ad_purchase_id=ad_purchase_id,
            slot_id=slot_id,
            invite_link=invite_link
        )
        await self.execute(query)
        return True

    async def get_subscriptions_count(self, ad_purchase_id: int, from_ts: int = None, to_ts: int = None) -> int:
        """Get total number of subscriptions for an ad purchase within a time range."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from sqlalchemy import func
        
        query = select(func.count(AdSubscription.id)).where(AdSubscription.ad_purchase_id == ad_purchase_id)
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        result = await self.fetchrow(query)
        return result if result else 0

    async def get_subscriptions_by_channel(self, ad_purchase_id: int, channel_id: int, from_ts: int = None, to_ts: int = None) -> list:
        """Get all subscriptions for a specific channel within a time range."""
        from main_bot.database.ad_purchase.model import AdSubscription
        
        query = select(AdSubscription).where(
            AdSubscription.ad_purchase_id == ad_purchase_id,
            AdSubscription.channel_id == channel_id
        )
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        return await self.fetch(query)

    async def get_subscriptions_by_slot(self, ad_purchase_id: int, slot_id: int, from_ts: int = None, to_ts: int = None) -> list:
        """Get all subscriptions for a specific slot within a time range."""
        from main_bot.database.ad_purchase.model import AdSubscription
        
        query = select(AdSubscription).where(
            AdSubscription.ad_purchase_id == ad_purchase_id,
            AdSubscription.slot_id == slot_id
        )
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        return await self.fetch(query)

    async def process_join_event(self, channel_id: int, user_id: int, invite_link: str) -> bool:
        """
        Process a join event and create a subscription if the invite link matches an ad purchase.
        Returns True if subscription was created.
        """
        # Find mapping by invite_link
        query = select(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.invite_link == invite_link)
        mapping = await self.fetchrow(query)
        
        if not mapping:
            return False
        
        # Add subscription
        return await self.add_subscription(
            user_id=user_id,
            channel_id=channel_id,
            ad_purchase_id=mapping.ad_purchase_id,
            slot_id=mapping.slot_id,
            invite_link=invite_link
        )



