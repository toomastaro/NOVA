from aiogram import Router, F, types
from aiogram.filters import ChatMemberUpdatedFilter
from main_bot.database.db import db
from main_bot.utils.error_handler import safe_handler
from sqlalchemy import select
from main_bot.database.ad_purchase.model import AdPurchaseLinkMapping
import logging

logger = logging.getLogger(__name__)

@safe_handler("Join Request Lead")
async def on_join_request(request: types.ChatJoinRequest):
    """
    Handle join requests to track Ad Leads.
    """
    if not request.invite_link:
        return

    logger.info(f"Received join request from {user_id} with link {invite_link}")
    
    # Check if this invite link belongs to an Ad Purchase
    # Use direct query to CRUD mixin or create specific method? CRUD mixin is better.
    # But CRUD mixin is on 'db' object.
    # We need to find mapping by invite_link.
    
    # Assuming db object has access to crud methods or we can execute query
    # db is instance of Database which inherits AdPurchaseCrud
    
    try:
        # We need a method to get specific mapping by link.
        # process_join_event logic uses select(AdPurchaseLinkMapping)
        # Let's add a helper in crud or just query here if possible?
        # Better to keep SQL in crud. But 'db' is main entry point.
        # Let's use `process_lead_event` logic similar to `process_join_event`.
        
        # Or just manually query since we are in handler and have access to db.
        # Ideally we add `process_lead_event` to CRUD.
        # But 'add_lead' exists.
        
        # Let's inspect create_emoji/process_join_event usage.
        # db.ad_purchase.process_join_event is used in set_resource. It queries mapping.
        
        # I will inline the logic here using db.fetchrow or similar, or better yet, add a method to CRUD.
        # But for now, let's query AdPurchaseLinkMapping directly.
        
        # However, accessing ORM models directly here is fine.
        
        # Find mapping
        query = select(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.invite_link == invite_link)
        mapping = await db.fetchrow(query)
        
        if mapping:
            # It's an ad link! Track lead.
            logger.info(f"Mapping found for link {invite_link}: Purchase {mapping.ad_purchase_id}, Slot {mapping.slot_id}")
            result = await db.ad_purchase.add_lead(
                user_id=user_id,
                ad_purchase_id=mapping.ad_purchase_id,
                slot_id=mapping.slot_id,
                ref_param=f"req_{mapping.ad_purchase_id}_{mapping.slot_id}" # Synthetic ref param
            )
            if result:
                 logger.info(f"Lead ADDED for user {user_id}")
            else:
                 logger.info(f"Lead SKIPPED (Duplicate) for user {user_id}")
        else:
            logger.info(f"No mapping found for link {invite_link}")
            
    except Exception as e:
        logger.error(f"Error processing join request for lead tracking: {e}")

def hand_join_request():
    router = Router()
    router.chat_join_request.register(on_join_request)
    return router
