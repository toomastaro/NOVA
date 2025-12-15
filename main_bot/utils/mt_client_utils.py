import logging
from pathlib import Path

from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def reset_client_task(client_id: int):
    logger.info(f"Starting reset for client {client_id}")
    
    # 1. Set status to RESETTING
    await db.mt_client.update_mt_client(
        client_id=client_id,
        status='RESETTING',
        is_active=False
    )
    
    client = await db.mt_client.get_mt_client(client_id)
    if not client:
        logger.error(f"Client {client_id} not found during reset")
        return

    # 2. Get all channels
    channels = await db.mt_client_channel.get_channels_by_client(client_id)
    
    # 3. Leave channels
    if Path(client.session_path).exists():
        async with SessionManager(Path(client.session_path)) as manager:
            for channel in channels:
                try:
                    logger.info(f"Client {client_id} leaving channel {channel.channel_id}")
                    await manager.leave_channel(channel.channel_id)
                except Exception as e:
                    logger.error(f"Error leaving channel {channel.channel_id} for client {client_id}: {e}")
    else:
        logger.warning(f"Session file not found for client {client_id}, skipping leave_channel")

    # 4. Delete MtClientChannel records
    await db.mt_client_channel.delete_channels_by_client(client_id)
    
    # 5. Reset MtClient fields
    await db.mt_client.update_mt_client(
        client_id=client_id,
        status='NEW',
        is_active=False,
        last_error_code=None,
        last_error_at=None,
        flood_wait_until=None
    )
    
    logger.info(f"Client {client_id} reset complete")
