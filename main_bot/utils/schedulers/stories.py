"""
Планировщик задач для отправки сторис в каналы.

Этот модуль содержит функции для:
- Отправки отложенных сторис
- Управления сторис через Telegram MT клиенты
"""
import asyncio
import logging
import os
from pathlib import Path

from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.story.model import Story
from main_bot.utils.functions import set_channel_session, get_path, get_path_video
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import StoryOptions
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def send_story(story: Story):
    """Отправить сторис в каналы"""
    options = StoryOptions(**story.story_options)

    if options.photo:
        options.photo = options.photo.file_id
    if options.video:
        options.video = options.video.file_id

    error_send = []
    success_send = []

    for chat_id in story.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        if channel.session_path:
            session_path = Path(channel.session_path)
        else:
            res = await set_channel_session(chat_id)
            if isinstance(res, dict) and res.get("success"):
                session_path = Path(res.get("session_path"))
            elif isinstance(res, Path):
                session_path = res
            else:
                session_path = None

        logger.info(f"Session path for {chat_id}: {session_path}")
        if isinstance(session_path, dict):
            session_path['chat_id'] = chat_id
            error_send.append(session_path)
            continue
        
        if not session_path:
             error_send.append({"chat_id": chat_id, "error": "Session Error"})
             continue

        manager = SessionManager(session_path)
        await manager.init_client()

        if not manager.client:
            await db.update_channel_by_chat_id(
                chat_id=chat_id,
                session_path=None
            )
            error_send.append({"chat_id": chat_id, "error": "Session Error"})
            continue
        
        try:
            me = await manager.me()
            if me:
                logger.info(f"📱 Posting story from client: user_id={me.id}, username={me.username or 'N/A'}, first_name={me.first_name}")
            else:
                logger.warning(f"Could not get client info for {session_path}")
        except Exception as e:
            logger.error(f"Error getting client info: {e}")

        try:
            can_post = await manager.can_send_stories(chat_id)
            if not can_post:
                error_send.append({"chat_id": chat_id, "error": "No Admin Rights"})
                await manager.close()
                continue
        except Exception as e:
            logger.error(f"Error during pre-flight checks for {chat_id}: {e}", exc_info=True)
            error_send.append({"chat_id": chat_id, "error": f"Check Error: {e}"})
            await manager.close()
            continue

        input_file = None
        if options.video:
            input_file = "main_bot/utils/temp/{}".format(
                (await bot.get_file(options.video)).file_path.split('/')[-1]
            )

        media_bytes = await bot.download(
            file=options.video or options.photo,
            destination=input_file
        )

        if options.photo:
            filepath = get_path(media_bytes, chat_id)
        else:
            filepath = get_path_video(input_file, chat_id)

        if options.caption:
            caption = options.caption
            options.caption = caption.replace(
                '<tg-emoji emoji-id', '<emoji id'
            ).replace(
                '</tg-emoji>', '</emoji>'
            )

        try:
            await manager.send_story(
                chat_id=chat_id,
                file_path=filepath,
                options=options
            )
            success_send.append({"chat_id": chat_id})
        except Exception as e:
            logger.error(f"Error sending story to {chat_id}: {e}", exc_info=True)
            error_str = str(e)
            error_send.append({"chat_id": chat_id, "error": error_str})

            if "CHAT_ADMIN_REQUIRED" in error_str or "STORIES_DISABLED" in error_str or "USER_NOT_PARTICIPANT" in error_str:
                from main_bot.utils.support_log import send_support_alert, SupportAlert
                from instance_bot import bot as main_bot_obj

                client = None
                if session_path:
                    clients = await db.get_mt_clients_by_pool('internal')
                    for c in clients:
                        if Path(c.session_path) == session_path:
                            client = c
                            break

                await send_support_alert(main_bot_obj, SupportAlert(
                    event_type='STORIES_PERMISSION_DENIED' if 'ADMIN' in error_str else 'INTERNAL_ACCESS_LOST',
                    client_id=client.id if client else None,
                    client_alias=client.alias if client else None,
                    pool_type='internal',
                    channel_id=chat_id,
                    channel_username=channel.username if channel else None,
                    is_our_channel=True,
                    task_id=story.id,
                    task_type='send_story',
                    error_code=error_str.split('(')[0].strip() if '(' in error_str else error_str[:50],
                    error_text=f"Не удалось отправить сторис: {error_str[:100]}"
                ))

        finally:
            try:
                os.remove(filepath)
                await manager.close()
            except Exception as e:
                logger.error(f"Error cleaning up story file {filepath}: {e}", exc_info=True)

    await db.clear_story(
        post_ids=[story.id]
    )

    if not story.report:
        return

    objects = await db.get_user_channels(
        user_id=story.admin_id,
        from_array=story.chat_ids
    )
    success_str = "\\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
    )
    error_str = "\\n".join(
        text("resource_title").format(
            obj.emoji_id,
            obj.title
        ) + " \\n{}".format(
            "".join(
                row.get("error")
                for row in error_send[:10]
                if row.get("chat_id") == obj.chat_id
            )
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
    )

    if success_send and error_send:
        message_text = text("success_error:story:public").format(
            success_str,
            error_str,
        )
    elif success_send:
        message_text = text("manage:story:success:public").format(
            success_str,
        )
    elif error_send:
        message_text = text("error:story:public").format(
            error_str,
        )
    else:
        message_text = "Unknown Story Notification Message"

    try:
        await bot.send_message(
            chat_id=story.admin_id,
            text=message_text
        )
    except Exception as e:
        logger.error(f"Error sending story report to admin {story.admin_id}: {e}", exc_info=True)


async def send_stories():
    """Периодическая задача: отправка отложенных сторис"""
    stories = await db.get_story_for_send()

    for story in stories:
        asyncio.create_task(send_story(story))
