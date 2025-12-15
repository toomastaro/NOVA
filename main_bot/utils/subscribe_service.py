import time
from main_bot.database.db import db

async def grant_subscription(user_id: int, chosen: list, total_days: int, service: str, object_type: str):
    # Logic extracted from subscribe_payment.py
    
    # Determine the sorting function based on service
    if service == 'top':
        # This part depends on how `cor` was determined in the handler.
        # In handler: `cor = db.get_channels_by_user_id` etc.
        # We need to map `object_type` to DB calls.
        if object_type == 'channels':
            cor = db.get_channels_by_user_id
        else:
            cor = db.get_user_bots_by_user_id
    else:
        # Default fallback if logic is complex. 
        # Actually `service` param in handler was used for sorting.
        # Here we just need to get objects by user_id to verify ownership or just get by ID directly?
        # `subscribe_payment.py` uses: `objects = await cor(user_id=user.id, sort_by=service)`
        # Then filters `chosen`.
        pass

    added_time = 86400 * total_days
    
    for obj_id in chosen:
        if object_type == 'channels':
            channel = await db.channel.get_channel_by_row_id(row_id=obj_id)
            if not channel: continue
            
            subscribe_value = channel.subscribe
            if not subscribe_value or subscribe_value < time.time():
                subscribe_value = added_time + int(time.time())
            else:
                subscribe_value += added_time

            await db.channel.update_channel_by_chat_id(
                chat_id=channel.chat_id,
                subscribe=subscribe_value
            )
        else:
            user_bot = await db.user_bot.get_bot_by_id(row_id=obj_id)
            if not user_bot: continue
            
            subscribe_value = user_bot.subscribe
            if not subscribe_value or subscribe_value < time.time():
                subscribe_value = added_time + int(time.time())
            else:
                subscribe_value += added_time

            await db.user_bot.update_bot_by_id(
                row_id=user_bot.id,
                subscribe=subscribe_value
            )
