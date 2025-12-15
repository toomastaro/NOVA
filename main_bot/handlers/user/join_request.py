from aiogram import Router, types
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

    user_id = request.from_user.id
    invite_link = request.invite_link.invite_link

    logger.info(f"Received join request from {user_id} with link {invite_link}")

    try:
        # Поиск маппинга ссылки к рекламной закупке
        query = select(AdPurchaseLinkMapping).where(
            AdPurchaseLinkMapping.invite_link == invite_link
        )
        mapping = await db.fetchrow(query)

        if mapping:
            logger.info(
                f"Mapping found for link {invite_link}: Purchase {mapping.ad_purchase_id}, Slot {mapping.slot_id}"
            )
            result = await db.ad_purchase.add_lead(
                user_id=user_id,
                ad_purchase_id=mapping.ad_purchase_id,
                slot_id=mapping.slot_id,
                ref_param=f"req_{mapping.ad_purchase_id}_{mapping.slot_id}",
            )
            if result:
                logger.info(f"Lead ADDED for user {user_id}")
            else:
                logger.info(f"Lead SKIPPED (Duplicate) for user {user_id}")
        else:
            logger.info(f"No mapping found for link {invite_link}")

    except Exception as e:
        logger.error(f"Error processing join request for lead tracking: {e}")


def get_router():
    router = Router()
    router.chat_join_request.register(on_join_request)
    return router
