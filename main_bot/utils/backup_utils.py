import logging
from aiogram import Bot, types
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.keyboards.keyboards import keyboards
from main_bot.utils.schemas import MessageOptions, Media
from config import Config
from instance_bot import bot

logger = logging.getLogger(__name__)

async def send_to_backup(post: Post) -> tuple[int | None, int | None]:
    """
    Sends the post to the backup channel.
    Returns (backup_chat_id, backup_message_id).
    """
    if not Config.BACKUP_CHAT_ID:
        return None, None

    message_options = MessageOptions(**post.message_options)
    
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
        message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = bot.send_video
        message_options.video = message_options.video.file_id
    else:
        cor = bot.send_animation
        message_options.animation = message_options.animation.file_id

    options = message_options.model_dump()
    # Clean up options for send method
    if message_options.text:
        options.pop("photo", None)
        options.pop("video", None)
        options.pop("animation", None)
        options.pop("show_caption_above_media", None)
        options.pop("has_spoiler", None)
        options.pop("caption", None)
    elif message_options.photo:
        options.pop("video", None)
        options.pop("animation", None)
        options.pop("text", None)
        options.pop("disable_web_page_preview", None)
    elif message_options.video:
        options.pop("photo", None)
        options.pop("animation", None)
        options.pop("text", None)
        options.pop("disable_web_page_preview", None)
    else: # animation
        options.pop("photo", None)
        options.pop("video", None)
        options.pop("text", None)
        options.pop("disable_web_page_preview", None)

    options['chat_id'] = Config.BACKUP_CHAT_ID
    options['parse_mode'] = 'HTML'

    try:
        backup_msg = await cor(
            **options,
            reply_markup=keyboards.post_kb(post=post)
        )
        return Config.BACKUP_CHAT_ID, backup_msg.message_id
    except Exception as e:
        logger.error(f"Error sending to backup channel: {e}", exc_info=True)
        return None, None

async def edit_backup_message(post: Post | PublishedPost, message_options: MessageOptions = None):
    """
    Updates the message in the backup channel to match the current post state.
    """
    if not post.backup_chat_id or not post.backup_message_id:
        return

    if not message_options:
        message_options = MessageOptions(**post.message_options)

    chat_id = post.backup_chat_id
    message_id = post.backup_message_id
    reply_markup = keyboards.post_kb(post=post)

    try:
        if message_options.text:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=message_options.text,
                parse_mode='HTML',
                disable_web_page_preview=message_options.disable_web_page_preview,
                reply_markup=reply_markup
            )
        else:
            # Media message
            if message_options.caption is not None:
                await bot.edit_message_caption(
                    chat_id=chat_id,
                    message_id=message_id,
                    caption=message_options.caption,
                    parse_mode='HTML',
                    reply_markup=reply_markup
                )
            else:
                # Just update markup if caption didn't change (or if we just want to update buttons)
                await bot.edit_message_reply_markup(
                    chat_id=chat_id,
                    message_id=message_id,
                    reply_markup=reply_markup
                )
                
    except Exception as e:
        logger.error(f"Error editing backup message {message_id} in {chat_id}: {e}", exc_info=True)

async def update_live_messages(post_id: int, message_options: MessageOptions, reply_markup=None):
    """
    Updates all live published messages for a given post_id.
    """
    published_posts = await db.get_published_posts_by_post_id(post_id)
    
    for post in published_posts:
        try:
            if message_options.text:
                await bot.edit_message_text(
                    chat_id=post.chat_id,
                    message_id=post.message_id,
                    text=message_options.text,
                    parse_mode='HTML',
                    disable_web_page_preview=message_options.disable_web_page_preview,
                    reply_markup=reply_markup
                )
            else:
                if message_options.caption is not None:
                    await bot.edit_message_caption(
                        chat_id=post.chat_id,
                        message_id=post.message_id,
                        caption=message_options.caption,
                        parse_mode='HTML',
                        reply_markup=reply_markup
                    )
                else:
                    await bot.edit_message_reply_markup(
                        chat_id=post.chat_id,
                        message_id=post.message_id,
                        reply_markup=reply_markup
                    )
        except Exception as e:
            logger.error(f"Error updating live message {post.message_id} in {post.chat_id}: {e}", exc_info=True)
