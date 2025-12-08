import logging
import traceback
from functools import wraps
from typing import Callable, Any

from aiogram import types
from aiogram.types import BufferedInputFile

from config import Config

logger = logging.getLogger(__name__)


async def send_error_report(bot, user_id: int, info: str, error: Exception, message: types.Message = None):
    """
    Sends a formatted error report to the backup channel.
    
    Args:
        bot: The bot instance.
        user_id: The ID of the user involved.
        info: Description of the stage/step where error occurred.
        error: The exception object.
        message: Optional message object to extract more context.
    """
    try:
        # Get user info if possible
        try:
            if message:
                chat = message.chat
                user = message.from_user
                username = f"@{user.username}" if user.username else "No username"
                user_link = f"<a href='tg://user?id={user.id}'>{user.full_name}</a>"
                channel_info = f"📺 {chat.title} (ID: {chat.id})" if chat.id != user.id else "👤 Private Chat"
            else:
                # If no message object, try to get basic info
                user_link = f"<a href='tg://user?id={user_id}'>User {user_id}</a>"
                username = "Unknown"
                channel_info = "Unknown"
        except Exception:
            user_link = f"ID: {user_id}"
            username = "Unknown"
            channel_info = "Unknown"

        # Format traceback
        tb = traceback.format_exc()
        if len(tb) > 3500:
            tb = tb[-3500:]  # Truncate if too long

        text = (
            f"🚨 <b>ERROR REPORT</b>\n\n"
            f"👤 <b>User</b>: {user_link} ({username})\n"
            f"📍 <b>Location</b>: {channel_info}\n"
            f"🛠 <b>Stage</b>: {info}\n"
            f"⚠️ <b>Error</b>: {str(error)}\n\n"
            f"📄 <b>Traceback</b>:\n"
            f"<blockquote expandable>{tb}</blockquote>"
        )

        if Config.BACKUP_CHAT_ID:
            await bot.send_message(Config.BACKUP_CHAT_ID, text)
        else:
            logger.warning("BACKUP_CHAT_ID not set, error report logged but not sent.")
            logger.error(text)

    except Exception as e:
        logger.error(f"Failed to send error report: {e}")
        logger.error(traceback.format_exc())


def safe_handler(stage_info: str):
    """
    Decorator to wrap handlers with try-except block and error reporting.
    
    Args:
         stage_info: A short description of the handler/step.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error in {stage_info}: {e}", exc_info=True)
                
                # Try to find message/callback in args to extract bot and user_id
                bot = None
                user_id = 0
                message = None
                
                for arg in args:
                    if isinstance(arg, (types.Message, types.CallbackQuery)):
                        bot = arg.bot
                        user_id = arg.from_user.id
                        message = arg if isinstance(arg, types.Message) else arg.message
                        break
                
                if bot:
                    await send_error_report(bot, user_id, stage_info, e, message)
                    
                    # Optional: Notify user
                    # try:
                    #     if isinstance(args[0], types.CallbackQuery):
                    #         await args[0].answer("❌ Произошла ошибка. Мы уже работаем над этим.", show_alert=True)
                    #     elif isinstance(args[0], types.Message):
                    #         await args[0].answer("❌ Произошла ошибка. Мы уже работаем над этим.")
                    # except:
                    #     pass
                        
                else:
                     logger.error("Could not determine bot instance to send report.")

        return wrapper
    return decorator
