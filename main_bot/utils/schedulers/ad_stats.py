import asyncio
import logging
import time
from sqlalchemy import select, and_

from main_bot.database.db import db
from main_bot.database.channel.model import Channel
from main_bot.database.ad_purchase.model import AdPurchase, AdPurchaseLinkMapping
from main_bot.database.types import AdTargetType
from config import config
from main_bot.database.mt_client_channel.crud import MtClientChannelCrud

logger = logging.getLogger(__name__)

async def ad_stats_worker():
    """
    Scheduler worker that periodically scans admin logs for active Ad Purchases
    belonging to users with at least one paid channel subscription.
    """
    
    # Get interval from env, default 600s
    interval = config.zakup_timer or 600
    logger.info(f"Ad Stats Worker started with interval {interval}s")
    
    while True:
        try:
            await process_ad_stats()
        except Exception as e:
            logger.error(f"Error in ad_stats_worker: {e}", exc_info=True)
        
        await asyncio.sleep(interval)

async def process_ad_stats():
    """
    Main processing logic.
    """
    current_time = int(time.time())
    
    # 1. Find users who have at least one active paid channel subscription
    # We query Channels directly
    query = select(Channel.admin_id).where(
        Channel.subscribe > current_time
    ).distinct()
    
    paid_admin_ids_rows = await db.fetch(query)
    paid_admin_ids = [row.admin_id for row in paid_admin_ids_rows]
    
    if not paid_admin_ids:
        # logger.debug("No paid admins found for ad stats scan.")
        return

    logger.info(f"Scanning ad stats for {len(paid_admin_ids)} paid admins")

    # 2. For these admins, find ACTIVE Ad Purchases
    query = select(AdPurchase).where(
        AdPurchase.owner_id.in_(paid_admin_ids),
        AdPurchase.status == "active"
    )
    active_purchases = await db.fetch(query)
    
    if not active_purchases:
        return

    # 3. For each purchase, get mappings
    for purchase in active_purchases:
        mappings = await db.get_link_mappings(purchase.id)
        
        # Group mappings by channel to minimize getAdminLog calls
        # Only interested in CHANNEL target type where tracking is enabled
        channel_mappings = {} # {channel_id: [mappings]}
        
        for m in mappings:
            if m.target_type == AdTargetType.CHANNEL and m.track_enabled and m.target_channel_id:
                if m.target_channel_id not in channel_mappings:
                    channel_mappings[m.target_channel_id] = []
                channel_mappings[m.target_channel_id].append(m)
        
        # Process each channel
        for channel_id, maps in channel_mappings.items():
            await process_channel_logs(channel_id, maps)

from pathlib import Path
from main_bot.utils.session_manager import SessionManager

# ... (imports)

from telethon import types, functions
from telethon.tl.types import (
    ChannelAdminLogEventActionParticipantJoinByInvite,
    ChannelAdminLogEventActionParticipantLeave,
    ChannelAdminLogEventActionParticipantJoin,
    ChannelAdminLogEventActionChangeTitle # example
)
from main_bot.utils.session_manager import SessionManager

# ... (imports from main_bot modules remain same)

async def process_channel_logs(channel_id: int, mappings: list[AdPurchaseLinkMapping]):
    """
    Fetch and process admin logs for a specific channel and verify against mappings.
    """
    client_model = await db.get_preferred_for_stats(channel_id)
    if not client_model:
        client_model = await db.get_any_client_for_channel(channel_id)
        
    if not client_model:
        return
    
    session_path = Path(client_model.session_path)
    if not session_path.exists():
        logger.warning(f"Session file not found for client {client_model.id}: {session_path}")
        return

    async with SessionManager(session_path) as manager:
        if not manager.client or not await manager.client.is_user_authorized():
            logger.warning(f"Could not load session for client {client_model.id} or not authorized")
            return
            
        client = manager.client # Telethon client

        min_scanned_id = min((m.last_scanned_id for m in mappings), default=0)
        
        try:
            # Telethon: iter_admin_log
            # We want join and leave events
            async for event in client.iter_admin_log(
                entity=channel_id,
                limit=None,
                min_id=min_scanned_id,
                join=True,
                leave=True,
                invite=True
            ):  
                # event is ChannelAdminLogEvent
                event_id = event.id
                user_id = event.user_id
                
                # --- JOIN BY INVITE ---
                if isinstance(event.action, ChannelAdminLogEventActionParticipantJoinByInvite):
                    invite_link = event.action.invite.link
                    # Telethon invite.link might be full URL or just hash? Usually full URL.
                    
                    if invite_link:
                        # Check if this link belongs to any mapping
                        for m in mappings:
                            if m.invite_link == invite_link:
                                await db.process_join_event(
                                    channel_id=channel_id,
                                    user_id=user_id,
                                    invite_link=invite_link
                                )
                                logger.info(f"Processed JOIN via AdminLog: User {user_id} -> Purchase {m.ad_purchase_id}")
                
                # --- LEAVE EVENT ---
                elif isinstance(event.action, ChannelAdminLogEventActionParticipantLeave):
                    # update_subscription_status handles logic by (user_id, channel_id)
                    await db.update_subscription_status(
                        user_id=user_id,
                        channel_id=channel_id,
                        status="left"
                    )
                    logger.info(f"Processed LEAVE via AdminLog: User {user_id} in Channel {channel_id}")


                # Update max scanned ID for ALL mappings of this channel
                for m in mappings:
                    if event_id > m.last_scanned_id:
                         from sqlalchemy import update
                         q = update(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.id == m.id).values(last_scanned_id=event_id)
                         await db.execute(q)
                         m.last_scanned_id = event_id 

        except Exception as e:
            logger.error(f"Error fetching admin log for channel {channel_id}: {e}")
