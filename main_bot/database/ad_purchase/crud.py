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
                    # Создаем ПОСТОЯННУЮ ссылку для отслеживания рекламы
                    invite = await bot.create_chat_invite_link(
                        chat_id=m.target_channel_id,
                        name=f"AdPurchase #{ad_purchase_id} Slot {m.slot_id}",
                        creates_join_request=False
                        # БЕЗ member_limit - ссылка постоянная для долгосрочного отслеживания
                    )
                    
                    # Update DB
                    query = update(AdPurchaseLinkMapping).where(
                        AdPurchaseLinkMapping.id == m.id
                    ).values(invite_link=invite.invite_link)
                    await self.execute(query)
                    
                    # Update local object
                    m.invite_link = invite.invite_link
                    logger.info(f"Created permanent invite link for purchase {ad_purchase_id}, slot {m.slot_id}, channel {m.target_channel_id}: {invite.invite_link}")
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


    async def get_global_stats(self, from_ts: int = None, to_ts: int = None) -> dict:
        """Get global statistics for all ad purchases."""
        from main_bot.database.ad_purchase.model import AdLead, AdSubscription
        from sqlalchemy import func
        
        # Count active purchases
        query = select(func.count(AdPurchase.id)).where(AdPurchase.status == "active")
        active_purchases = await self.fetchrow(query)
        
        # Count total leads
        query = select(func.count(AdLead.id))
        if from_ts:
            query = query.where(AdLead.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdLead.created_timestamp <= to_ts)
        total_leads = await self.fetchrow(query)
        
        # Count total subscriptions
        query = select(func.count(AdSubscription.id))
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        total_subs = await self.fetchrow(query)
        
        return {
            "active_purchases": active_purchases if active_purchases else 0,
            "total_leads": total_leads if total_leads else 0,
            "total_subscriptions": total_subs if total_subs else 0
        }

    async def get_top_purchases(self, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top purchases by subscription count."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from sqlalchemy import func
        
        query = select(
            AdPurchase.id,
            AdPurchase.comment,
            func.count(AdSubscription.id).label('subs_count')
        ).join(
            AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id
        )
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdPurchase.id, AdPurchase.comment).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)

    async def get_top_creatives(self, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top creatives by subscription count."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from main_bot.database.ad_creative.model import AdCreative
        from sqlalchemy import func
        
        query = select(
            AdCreative.id,
            AdCreative.name,
            func.count(AdSubscription.id).label('subs_count')
        ).join(
            AdPurchase, AdCreative.id == AdPurchase.creative_id
        ).join(
            AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id
        )
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdCreative.id, AdCreative.name).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)

    async def get_top_channels(self, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top channels by subscription count."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from sqlalchemy import func
        
        query = select(
            AdSubscription.channel_id,
            func.count(AdSubscription.id).label('subs_count')
        )
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdSubscription.channel_id).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)


    async def get_user_global_stats(self, user_id: int, from_ts: int = None, to_ts: int = None) -> dict:
        """Get global statistics for user's ad purchases."""
        from main_bot.database.ad_purchase.model import AdLead, AdSubscription
        from sqlalchemy import func
        
        # Count active purchases for this user
        query = select(func.count(AdPurchase.id)).where(
            AdPurchase.owner_id == user_id,
            AdPurchase.status == "active"
        )
        active_purchases = await self.fetchrow(query)
        
        # Count total leads for user's purchases
        query = select(func.count(AdLead.id)).join(
            AdPurchase, AdLead.ad_purchase_id == AdPurchase.id
        ).where(AdPurchase.owner_id == user_id)
        
        if from_ts:
            query = query.where(AdLead.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdLead.created_timestamp <= to_ts)
        total_leads = await self.fetchrow(query)
        
        # Count total subscriptions for user's purchases
        query = select(func.count(AdSubscription.id)).join(
            AdPurchase, AdSubscription.ad_purchase_id == AdPurchase.id
        ).where(AdPurchase.owner_id == user_id)
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        total_subs = await self.fetchrow(query)
        
        return {
            "active_purchases": active_purchases if active_purchases else 0,
            "total_leads": total_leads if total_leads else 0,
            "total_subscriptions": total_subs if total_subs else 0
        }

    async def get_user_top_purchases(self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top purchases by subscription count for a specific user."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from sqlalchemy import func
        
        query = select(
            AdPurchase.id,
            AdPurchase.comment,
            func.count(AdSubscription.id).label('subs_count')
        ).join(
            AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id
        ).where(AdPurchase.owner_id == user_id)
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdPurchase.id, AdPurchase.comment).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)

    async def get_user_top_creatives(self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top creatives by subscription count for a specific user."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from main_bot.database.ad_creative.model import AdCreative
        from sqlalchemy import func
        
        query = select(
            AdCreative.id,
            AdCreative.name,
            func.count(AdSubscription.id).label('subs_count')
        ).join(
            AdPurchase, AdCreative.id == AdPurchase.creative_id
        ).join(
            AdSubscription, AdPurchase.id == AdSubscription.ad_purchase_id
        ).where(AdCreative.owner_id == user_id)
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdCreative.id, AdCreative.name).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)

    async def get_user_top_channels(self, user_id: int, from_ts: int = None, to_ts: int = None, limit: int = 5) -> list:
        """Get top channels by subscription count for a specific user."""
        from main_bot.database.ad_purchase.model import AdSubscription
        from sqlalchemy import func
        
        query = select(
            AdSubscription.channel_id,
            func.count(AdSubscription.id).label('subs_count')
        ).join(
            AdPurchase, AdSubscription.ad_purchase_id == AdPurchase.id
        ).where(AdPurchase.owner_id == user_id)
        
        if from_ts:
            query = query.where(AdSubscription.created_timestamp >= from_ts)
        if to_ts:
            query = query.where(AdSubscription.created_timestamp <= to_ts)
        
        query = query.group_by(AdSubscription.channel_id).order_by(func.count(AdSubscription.id).desc()).limit(limit)
        
        return await self.fetch(query)





