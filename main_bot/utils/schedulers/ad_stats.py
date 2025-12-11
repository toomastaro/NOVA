import asyncio
import logging
import time
from sqlalchemy import select, and_
from pyrogram.enums import ChatEventAction

from main_bot.database.db import db
from main_bot.database.channel.model import Channel
from main_bot.database.ad_purchase.model import AdPurchase, AdPurchaseLinkMapping
from main_bot.database.types import AdTargetType
from config import config
from main_bot.database.mt_client_channel.crud import MtClientChannelCrud
from main_bot.utils.client_manager import client_manager

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

async def process_channel_logs(channel_id: int, mappings: list[AdPurchaseLinkMapping]):
    """
    Fetch and process admin logs for a specific channel and verify against mappings.
    """
    # 1. Get MTProto client for this channel
    # We need a client that is admin. 
    # Use db.get_mt_client_for_channel helper if exists, or manually via MtClientChannel
    
    # Assuming get_any_client_for_channel returns a client model, then we get the active session from manager
    # We strictly need a client that is IN the channel and IS admin.
    # Ideally, we used the one associated with the channel.
    
    # Quick way: get preferred or any
    client_model = await db.get_preferred_for_stats(channel_id)
    if not client_model:
        client_model = await db.get_any_client_for_channel(channel_id)
        
    if not client_model:
        logger.warning(f"No MTClient found for channel {channel_id} (Ad Stats)")
        return

    session = await client_manager.get_client(client_model.id)
    if not session:
        logger.warning(f"Could not load session for client {client_model.id}")
        return

    # 2. Determine min_id (start from the oldest last_scanned_id among mappings)
    # Actually, we should process from the minimum last_scanned_id, 
    # but updates might be different per mapping if they were added at different times?
    # Usually they are independent. But getAdminLog is per channel.
    # Usage: get_admin_log(channel_id, min_id=...)
    
    min_scanned_id = min((m.last_scanned_id for m in mappings), default=0)
    
    try:
        # Fetch events: Join and Leave (and Invites if needed to Correlation? Join event usually contains invite link)
        # We need invite link usage info.
        # Pyrogram: get_admin_log
        async for event in session.get_admin_log(
            chat_id=channel_id, 
            action_filter=ChatEventAction.JOIN_BY_INVITE | ChatEventAction.LEFT | ChatEventAction.MEMBER_INVITED,
            min_id=min_scanned_id,
            limit=0 # No limit, fetch all new
        ):
            # Process event
            event_id = event.id
            
            # --- JOIN EVENT ---
            if event.action == ChatEventAction.JOIN_BY_INVITE:
                invite_link = event.invite_link.invite_link if event.invite_link else None
                user = event.user
                
                if invite_link and user:
                    # Check if this link belongs to any mapping
                    for m in mappings:
                        if m.invite_link == invite_link:
                            # Match found! Confirmed Subscription.
                            await db.process_join_event(
                                channel_id=channel_id,
                                user_id=user.id,
                                invite_link=invite_link
                            )
                            # process_join_event now handles add_lead + add_sub logic safely
                            logger.info(f"Processed JOIN via AdminLog: User {user.id} -> Purchase {m.ad_purchase_id}")
            
            # --- LEAVE EVENT (Member Left or Kicked) ---
            elif event.action in [ChatEventAction.LEFT, ChatEventAction.MEMBER_KICKED]:
                user = event.user
                if user:
                    # We don't know WHICH mapping they belonged to without looking up DB.
                    # But update_subscription_status handles logic by (user_id, channel_id).
                    # It updates ALL purchase subs for this user in this channel to 'left'.
                    await db.update_subscription_status(
                        user_id=user.id,
                        channel_id=channel_id,
                        status="left"
                    )
                    logger.info(f"Processed LEAVE via AdminLog: User {user.id} in Channel {channel_id}")

            # Update max scanned ID for ALL mappings of this channel
            # Use max() to ensure we move forward
            for m in mappings:
                if event_id > m.last_scanned_id:
                     # Update DB (we need a direct update method or use update query)
                     # Using raw query for efficiency or add method in CRUD
                     # Just execute update here
                     from sqlalchemy import update
                     q = update(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.id == m.id).values(last_scanned_id=event_id)
                     await db.execute(q)
                     m.last_scanned_id = event_id # Update local

    except Exception as e:
        logger.error(f"Error fetching admin log for channel {channel_id}: {e}")
