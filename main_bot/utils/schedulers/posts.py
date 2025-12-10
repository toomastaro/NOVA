"""
Планировщик задач для отправки, удаления и управления постами в каналах.

Этот модуль содержит функции для:
- Отправки отложенных постов
- Удаления постов по расписанию
- Открепления постов
- Проверки и отправки CPM отчетов (24/48/72 часа)
"""
import asyncio
import logging
import os
import time
from pathlib import Path

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from config import Config
from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.keyboards import keyboards
from main_bot.utils.functions import set_channel_session
from main_bot.utils.lang.language import text
from main_bot.utils.schemas import MessageOptions
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def get_views_for_post(post):
    """Получить количество просмотров для поста"""
    channel = await db.get_channel_by_chat_id(post.chat_id)
    session_path = None
    if channel.session_path:
        session_path = Path(channel.session_path)
    else:
        res = await set_channel_session(post.chat_id)
        if isinstance(res, dict) and res.get("success"):
            session_path = Path(res.get("session_path"))
        elif isinstance(res, Path):
            session_path = res

    views = 0
    if session_path:
        async with SessionManager(session_path) as session:
            if session:
                views_obj = await session.get_views(post.chat_id, [post.message_id])
                if views_obj:
                    views = sum([i.views for i in views_obj.views])
    return views, channel


async def send(post: Post):
    """Отправить пост в каналы"""
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
    if message_options.text:
        options.pop("photo")
        options.pop("video")
        options.pop("animation")
        options.pop("show_caption_above_media")
        options.pop("has_spoiler")
        options.pop("caption")
    elif message_options.photo:
        options.pop("video")
        options.pop("animation")
        options.pop("text")
        options.pop("disable_web_page_preview")
    elif message_options.video:
        options.pop("photo")
        options.pop("animation")
        options.pop("text")
        options.pop("disable_web_page_preview")
    # animation
    else:
        options.pop("photo")
        options.pop("video")
        options.pop("text")
        options.pop("disable_web_page_preview")

    options['parse_mode'] = 'HTML'

    error_send = []
    success_send = []

    # Backup Logic
    backup_message_id = post.backup_message_id
    if Config.BACKUP_CHAT_ID:
        if not backup_message_id:
            try:
                options['chat_id'] = Config.BACKUP_CHAT_ID
                options['parse_mode'] = 'HTML'
                
                backup_msg = await cor(
                    **options,
                    reply_markup=keyboards.post_kb(post=post)
                )
                backup_message_id = backup_msg.message_id
                
                await db.update_post(
                    post_id=post.id,
                    backup_chat_id=Config.BACKUP_CHAT_ID,
                    backup_message_id=backup_message_id
                )
                logger.info(f"Created backup for post {post.id}: chat={Config.BACKUP_CHAT_ID}, msg={backup_message_id}")
            except Exception as e:
                logger.error(f"Error creating backup for post {post.id}: {e}", exc_info=True)
                pass

    for chat_id in post.chat_ids:
        channel = await db.get_channel_by_chat_id(chat_id)
        if not channel.subscribe:
            continue

        try:
            if backup_message_id and Config.BACKUP_CHAT_ID:
                post_message = await bot.copy_message(
                    chat_id=chat_id,
                    from_chat_id=Config.BACKUP_CHAT_ID,
                    message_id=backup_message_id,
                    reply_markup=keyboards.post_kb(post=post),
                    parse_mode='HTML'
                )
                logger.info(f"Copied post {post.id} (backup {backup_message_id}) to {chat_id} (msg {post_message.message_id})")
            else:
                options['chat_id'] = chat_id
                post_message = await cor(
                    **options,
                    reply_markup=keyboards.post_kb(post=post)
                )
                logger.info(f"Directly sent post {post.id} to {chat_id} (msg {post_message.message_id})")

            await asyncio.sleep(0.25)
        except Exception as e:
            logger.error(f"Error sending post {post.id} to {chat_id}: {e}", exc_info=True)
            error_send.append({"chat_id": chat_id, "error": str(e)})
            continue

        if post.pin_time:
            try:
                await bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=post_message.message_id,
                    disable_notification=message_options.disable_notification
                )
            except Exception as e:
                logger.error(f"Error pinning message {post_message.message_id} in {chat_id}: {e}", exc_info=True)

        current_time = int(time.time())
        success_send.append(
            {
                "post_id": post.id,
                "chat_id": chat_id,
                "message_id": post_message.message_id,
                "admin_id": post.admin_id,
                "reaction": post.reaction or None,
                "hide": post.hide or None,
                "buttons": post.buttons or None,

                "delete_time": post.delete_time + current_time if post.delete_time else None,
                "report": post.report,
                "cpm_price": post.cpm_price,

                "backup_chat_id": Config.BACKUP_CHAT_ID if backup_message_id else None,
                "backup_message_id": backup_message_id,
                "message_options": post.message_options
            }
        )

    if success_send:
        await db.add_many_published_post(
            posts=success_send
        )

    await db.clear_posts(
        post_ids=[post.id]
    )

    if not post.report:
        return

    import html
    objects = await db.get_user_channels(
        user_id=post.admin_id,
        from_array=post.chat_ids
    )
    
    # Format Success List
    success_str_inner = "\n".join(
        text("resource_title").format(
            obj.emoji_id,
            html.escape(obj.title)
        ) for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
    )
    success_str = f"<blockquote expandable>{success_str_inner}</blockquote>" if success_str_inner else ""

    # Format Error List
    error_str_inner = "\n".join(
         text("resource_title").format(
            obj.emoji_id,
            html.escape(obj.title)
        ) + f" \n{''.join(row.get('error') for row in error_send[:10] if row.get('chat_id') == obj.chat_id)}"
        for obj in objects
        if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
    )
    error_str = f"<blockquote expandable>{error_str_inner}</blockquote>" if error_str_inner else ""

    if success_send and error_send:
        message_text = text("success_error:post:public").format(
            success_str,
            error_str,
        )
    elif success_send:
        message_text = text("manage:post:success:public").format(
            success_str,
        )
    elif error_send:
        message_text = text("error:post:public").format(
            error_str,
        )
    else:
        message_text = "Unknown Post Notification Message"

    try:
        await bot.send_message(
            chat_id=post.admin_id,
            text=message_text,
            reply_markup=keyboards.posting_menu()
        )
    except Exception as e:
        logger.error(f"Error sending report to admin {post.admin_id}: {e}", exc_info=True)


async def send_posts():
    """Периодическая задача: отправка отложенных постов"""
    posts = await db.get_post_for_send()

    for post in posts:
        asyncio.create_task(send(post))


async def unpin_posts():
    """Периодическая задача: открепление постов"""
    posts = await db.get_posts_for_unpin()

    for post in posts:
        try:
            await bot.unpin_chat_message(
                chat_id=post.chat_id,
                message_id=post.message_id
            )
        except Exception as e:
            logger.error(f"Error unpinning message {post.message_id} in {post.chat_id}: {e}", exc_info=True)


async def check_cpm_reports():
    """Периодическая задача: проверка и отправка CPM отчетов за 24/48/72 часа"""
    from sqlalchemy import select, update
    from main_bot.database.published_post.model import PublishedPost
    from main_bot.utils.report_signature import get_report_signatures
    import html
    
    current_time = int(time.time())
    
    # Получаем посты с CPM ценой, которые еще не удалены
    stmt = select(PublishedPost).where(
        PublishedPost.cpm_price.is_not(None),
        PublishedPost.deleted_at.is_(None)
    )
    posts = await db.fetch(stmt)
    
    for post in posts:
        try:
            elapsed = current_time - post.created_timestamp
            
            report_needed = False
            period = ""
            
            if elapsed >= 24 * 3600 and not post.report_24h_sent:
                period = "24h"
                report_needed = True
            elif elapsed >= 48 * 3600 and not post.report_48h_sent:
                period = "48h"
                report_needed = True
            elif elapsed >= 72 * 3600 and not post.report_72h_sent:
                period = "72h"
                report_needed = True
            
            if not report_needed:
                continue

            views, channel = await get_views_for_post(post)
            
            # Обновление БД
            updates = {}
            if period == "24h":
                updates = {"views_24h": views, "report_24h_sent": True}
            elif period == "48h":
                updates = {"views_48h": views, "report_48h_sent": True}
            elif period == "72h":
                updates = {"views_72h": views, "report_72h_sent": True}
            
            stmt = update(PublishedPost).where(PublishedPost.id == post.id).values(**updates)
            await db.execute(stmt)
            
            # Отправка отчета
            cpm_price = post.cpm_price
            rub_price = round(float(cpm_price * float(views / 1000)), 2)
            
            user = await db.get_user(post.admin_id)
            usd_rate = 1.0
            if user and user.default_exchange_rate_id:
                exchange_rate = await db.get_exchange_rate(user.default_exchange_rate_id)
                if exchange_rate and exchange_rate.rate > 0:
                    usd_rate = exchange_rate.rate

            channels_text = text("resource_title").format(html.escape(channel.title)) + f" - 👀 {views}"
            channels_text = f"<blockquote expandable>{channels_text}</blockquote>"
            
            full_report = text("cpm:report:header").format(post.post_id, period) + "\n"
            full_report += text("cpm:report:stats").format(
                period,
                views,
                rub_price,
                round(rub_price / usd_rate, 2),
                round(usd_rate, 2)
            ) + "\n\n" + channels_text
            
            # Добавляем подпись
            full_report += await get_report_signatures(user, 'cpm', bot)
            
            await bot.send_message(
                chat_id=post.admin_id,
                text=full_report
            )
            
        except Exception as e:
            logger.error(f"Ошибка при обработке CPM отчета для поста {post.id}: {e}", exc_info=True)


async def delete_posts():
    """Периодическая задача: удаление постов по расписанию"""
    from main_bot.utils.report_signature import get_report_signatures
    import html

    db_posts = await db.get_posts_for_delete()

    row_ids = []
    posts = {}
    for post in db_posts:
        views, channel = await get_views_for_post(post)

        if post.post_id not in posts:
            posts[post.post_id] = []

        messages = posts[post.post_id]
        messages.append({
            "channel": channel,
            "views": views,
            "admin_id": post.admin_id,
            "cpm_price": post.cpm_price,
            "post_obj": post
        })
        posts[post.post_id] = messages

        try:
            await bot.delete_message(post.chat_id, post.message_id)
        except Exception as e:
            logger.error(f"Error deleting message {post.message_id} in {post.chat_id}: {e}", exc_info=True)
            try:
                await bot.send_message(
                    chat_id=post.admin_id,
                    text=text("error:post:delete").format(
                        post.message_id,
                        channel.emoji_id,
                        channel.title
                    )
                )
            except Exception as e:
                logger.error(f"Error sending delete error report to admin {post.admin_id}: {e}", exc_info=True)

        row_ids.append(post.id)

    for post_id, message_objects in posts.items():
        cpm_price = message_objects[0]["cpm_price"]
        if not cpm_price:
            continue

        admin_id = message_objects[0]["admin_id"]
        
        user = await db.get_user(admin_id)
        usd_rate = 1.0
        exchange_rate_update_time = None
        if user and user.default_exchange_rate_id is not None:
            exchange_rate = await db.get_exchange_rate(user.default_exchange_rate_id)
            if exchange_rate and exchange_rate.rate > 0:
                usd_rate = exchange_rate.rate
                exchange_rate_update_time = exchange_rate.last_update

        total_views = sum(obj["views"] for obj in message_objects)
        rub_price = round(float(cpm_price * float(total_views / 1000)), 2)
        
        channels_text_inner = "\n".join(
            text("resource_title").format(html.escape(obj["channel"].title)) + f" - 👀 {obj['views']}"
            for obj in message_objects
        )
        channels_text = f"<blockquote expandable>{channels_text_inner}</blockquote>"

        try:
            representative_post = message_objects[0]["post_obj"]
            delete_duration = representative_post.delete_time - representative_post.created_timestamp
            views_24 = representative_post.views_24h
            views_48 = representative_post.views_48h
            
            def format_report(title_suffix, current_views, v24=None, v48=None):
                lines = []
                lines.append(text("cpm:report:header").format(post_id, title_suffix))
                lines.append(text("cpm:report:stats").format(
                    "Финальный" if "Final" in title_suffix else title_suffix,
                    current_views,
                    rub_price,
                    round(rub_price / usd_rate, 2),
                    round(usd_rate, 2)
                ))
                if v24 is not None:
                     rub_24 = round(float(cpm_price * float(v24 / 1000)), 2)
                     lines.append(text("cpm:report:history_row").format("24ч", v24, rub_24))
                if v48 is not None:
                     rub_48 = round(float(cpm_price * float(v48 / 1000)), 2)
                     lines.append(text("cpm:report:history_row").format("48ч", v48, rub_48))
                lines.append("\n" + channels_text)
                return "\n".join(lines)

            report_text = ""
            hours = int(delete_duration / 3600)
            
            if delete_duration < 24 * 3600:
                 report_text = text("cpm:report").format(
                    post_id,
                    channels_text,
                    cpm_price,
                    total_views,
                    rub_price,
                    round(rub_price / usd_rate, 2),
                    round(usd_rate, 2),
                    exchange_rate_update_time.strftime("%H:%M %d.%m.%Y") if exchange_rate_update_time else "N/A"
                )
            elif delete_duration <= 48 * 3600:
                report_text = format_report(f"Final ({hours}ч)", total_views, views_24)
            else:
                report_text = format_report(f"Final ({hours}ч)", total_views, views_24, views_48)
            
            if not report_text:
                 report_text = text("cpm:report").format(
                    post_id,
                    channels_text,
                    cpm_price,
                    total_views,
                    rub_price,
                    round(rub_price / usd_rate, 2),
                    round(usd_rate, 2),
                    exchange_rate_update_time.strftime("%H:%M %d.%m.%Y") if exchange_rate_update_time else "N/A"
                )

            # Добавляем подпись
            report_text += await get_report_signatures(user, 'cpm', bot)
            
            await bot.send_message(
                chat_id=admin_id,
                text=report_text
            )
        except Exception as e:
            logger.error(f"Error sending CPM report to admin {admin_id}: {e}", exc_info=True)

    await db.soft_delete_published_posts(
        row_ids=row_ids
    )


def register_post_jobs(scheduler: AsyncIOScheduler):
    """
    Регистрация системных периодических задач для постов.
    
    Использует replace_existing=True для предотвращения дублей при перезапуске.
    """
    # Отправка отложенных постов (каждые 10 секунд)
    scheduler.add_job(
        func=send_posts,
        trigger=CronTrigger(second='*/10'),
        id="send_posts_periodic",
        replace_existing=True,
        name="Отправка отложенных постов"
    )
    
    # Открепление постов (каждые 10 секунд)
    scheduler.add_job(
        func=unpin_posts,
        trigger=CronTrigger(second='*/10'),
        id="unpin_posts_periodic",
        replace_existing=True,
        name="Открепление постов"
    )
    
    # Удаление постов (каждые 10 секунд)
    scheduler.add_job(
        func=delete_posts,
        trigger=CronTrigger(second='*/10'),
        id="delete_posts_periodic",
        replace_existing=True,
        name="Удаление постов по расписанию"
    )
    
    # Проверка CPM отчетов (каждые 10 секунд)
    scheduler.add_job(
        func=check_cpm_reports,
        trigger=CronTrigger(second='*/10'),
        id="check_cpm_reports_periodic",
        replace_existing=True,
        name="Проверка CPM отчетов 24/48/72ч"
    )
    
    logger.info("Зарегистрированы системные задачи для постов")
