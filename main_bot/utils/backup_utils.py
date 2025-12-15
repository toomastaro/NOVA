import logging
from aiogram import Bot, types
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.database.story.model import Story
from main_bot.database.bot_post.model import BotPost
from main_bot.keyboards import keyboards
from main_bot.utils.schemas import MessageOptions, Media
from config import Config
from instance_bot import bot

logger = logging.getLogger(__name__)

async def send_to_backup(post: Post | Story | BotPost) -> tuple[int | None, int | None]:
    """
    Sends the post to the backup channel.
    Returns (backup_chat_id, backup_message_id).
    """
    if not Config.BACKUP_CHAT_ID:
        return None, None

    if isinstance(post, Post):
        message_options = MessageOptions(**post.message_options)
        reply_markup = keyboards.post_kb(post=post)
    elif isinstance(post, Story):
        # Filter fields to match MessageOptions
        story_dump = post.story_options.copy() if hasattr(post.story_options, 'copy') else dict(post.story_options)
        valid_fields = MessageOptions.model_fields.keys()
        filtered_story_options = {k: v for k, v in story_dump.items() if k in valid_fields}
        
        message_options = MessageOptions(**filtered_story_options)
        reply_markup = keyboards.story_kb(post=post)
    elif isinstance(post, BotPost):
        from main_bot.utils.schemas import MessageOptionsHello
        message_options = MessageOptionsHello(**post.message)
        reply_markup = keyboards.bot_post_kb(post=post)
    else:
        return None, None
    
    if message_options.text:
        cor = bot.send_message
    elif message_options.photo:
        cor = bot.send_photo
        # Handle both Media object and string (file_id)
        if hasattr(message_options.photo, 'file_id'):
            message_options.photo = message_options.photo.file_id
    elif message_options.video:
        cor = bot.send_video
        if hasattr(message_options.video, 'file_id'):
            message_options.video = message_options.video.file_id
    else:
        cor = bot.send_animation
        if hasattr(message_options.animation, 'file_id'):
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
    options.pop('reply_markup', None)

    try:
        backup_msg = await cor(
            **options,
            reply_markup=reply_markup
        )
        return Config.BACKUP_CHAT_ID, backup_msg.message_id
    except Exception as e:
        logger.error(f"Error sending to backup channel: {e}", exc_info=True)
        return None, None

async def edit_backup_message(post: Post | PublishedPost | Story | BotPost, message_options: MessageOptions = None):
    """
    Updates the message in the backup channel to match the current post state.
    """
    if not post or not post.backup_chat_id or not post.backup_message_id:
        return

    if not message_options:
        if isinstance(post, (Post, PublishedPost)):
            message_options = MessageOptions(**post.message_options)
            reply_markup = keyboards.post_kb(post=post)
        elif isinstance(post, Story):
            # Filter fields
            story_dump = post.story_options.copy() if hasattr(post.story_options, 'copy') else dict(post.story_options)
            valid_fields = MessageOptions.model_fields.keys()
            filtered = {k: v for k, v in story_dump.items() if k in valid_fields}
            
            message_options = MessageOptions(**filtered)
            reply_markup = keyboards.manage_story(post=post)
        elif isinstance(post, BotPost):
            from main_bot.utils.schemas import MessageOptionsHello
            message_options = MessageOptionsHello(**post.message)
            reply_markup = keyboards.manage_bot_post(post=post)
    else:
        # If message_options provided, we still need correct markup
        if isinstance(post, (Post, PublishedPost)):
             reply_markup = keyboards.post_kb(post=post)
        elif isinstance(post, Story):
             reply_markup = keyboards.manage_story(post=post)
        elif isinstance(post, BotPost):
             reply_markup = keyboards.manage_bot_post(post=post)
        else:
             reply_markup = None

    chat_id = post.backup_chat_id
    message_id = post.backup_message_id

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
        logger.error(f"Error editing backup message {message_id} in {chat_id}: {e}. Attempting fallback (delete and resend).")
        try:
            # Fallback: Delete and Resend to Backup
            try:
                await bot.delete_message(chat_id, message_id)
            except Exception as del_e:
                logger.warning(f"Failed to delete backup message {message_id}: {del_e}")

            # Send new message to backup
            # We need to construct options for send_message/photo/etc.
            # Reuse send_to_backup logic or similar? 
            # send_to_backup takes a Post object. We have Post or PublishedPost.
            # Let's construct a temporary Post object or just use the options manually.
            
            # Helper to send based on options
            if message_options.text:
                cor = bot.send_message
                send_options = message_options.model_dump(exclude={"photo", "video", "animation", "show_caption_above_media", "has_spoiler", "caption", "reply_markup"})
            elif message_options.photo:
                cor = bot.send_photo
                send_options = message_options.model_dump(exclude={"video", "animation", "text", "disable_web_page_preview", "reply_markup"})
                send_options["photo"] = message_options.photo.file_id if isinstance(message_options.photo, Media) else message_options.photo
            elif message_options.video:
                cor = bot.send_video
                send_options = message_options.model_dump(exclude={"photo", "animation", "text", "disable_web_page_preview", "reply_markup"})
                send_options["video"] = message_options.video.file_id if isinstance(message_options.video, Media) else message_options.video
            else:
                cor = bot.send_animation
                send_options = message_options.model_dump(exclude={"photo", "video", "text", "disable_web_page_preview", "reply_markup"})
                send_options["animation"] = message_options.animation.file_id if isinstance(message_options.animation, Media) else message_options.animation

            send_options['chat_id'] = chat_id
            send_options['parse_mode'] = 'HTML'
            send_options['reply_markup'] = reply_markup

            new_backup_msg = await cor(**send_options)
            new_backup_message_id = new_backup_msg.message_id
            
            # Update DB
            post_id = post.post_id if isinstance(post, PublishedPost) else post.id
            
            # Update Post
            if isinstance(post, Story):
                 await db.story.update_story(post.id, backup_message_id=new_backup_message_id)
            elif isinstance(post, BotPost):
                 await db.bot_post.update_bot_post(post.id, backup_message_id=new_backup_message_id)
            elif isinstance(post, (Post, PublishedPost)):
                 # Update Post
                await db.post.update_post(
                    post_id=post_id,
                    backup_message_id=new_backup_message_id
                )
                
                # Update all PublishedPosts
                await db.published_post.update_published_posts_by_post_id(
                    post_id=post_id,
                    backup_message_id=new_backup_message_id
                )
            
            logger.info(f"Backup fallback successful: Replaced {message_id} with {new_backup_message_id} for post {post_id}")

        except Exception as fallback_e:
            logger.error(f"Backup fallback failed for post {post.id if hasattr(post, 'id') else '?'}: {fallback_e}", exc_info=True)

async def update_live_messages(post_id: int, message_options: MessageOptions, reply_markup=None):
    """
    Updates all live published messages for a given post_id.
    """
    published_posts = await db.published_post.get_published_posts_by_post_id(post_id)
    
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
            logger.error(f"Error updating live message {post.message_id} in {post.chat_id}: {e}. Attempting fallback (delete and repost).")
            try:
                # Fallback: Delete and Copy from Backup
                try:
                    await bot.delete_message(post.chat_id, post.message_id)
                except Exception as del_e:
                    logger.warning(f"Failed to delete message {post.message_id} in {post.chat_id}: {del_e}")

                if post.backup_chat_id and post.backup_message_id:
                    new_msg = await bot.copy_message(
                        chat_id=post.chat_id,
                        from_chat_id=post.backup_chat_id,
                        message_id=post.backup_message_id,
                        reply_markup=reply_markup,
                        parse_mode='HTML'
                    )
                    
                    # Update PublishedPost with new message_id
                    await db.published_post.update_published_post(
                        post_id=post.id,
                        message_id=new_msg.message_id
                    )
                    logger.info(f"Fallback successful: Replaced message {post.message_id} with {new_msg.message_id} in {post.chat_id}")
                else:
                    logger.error(f"Fallback failed: No backup info for post {post.id}")

            except Exception as fallback_e:
                logger.error(f"Fallback failed for {post.chat_id}: {fallback_e}", exc_info=True)
            
    logger.info(f"Updated {len(published_posts)} live messages for post {post_id}")
