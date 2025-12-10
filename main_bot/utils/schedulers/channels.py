import asyncio
import logging
import time
from datetime import datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telethon.tl import functions, types

from main_bot.database.db import db
from main_bot.utils.novastat import novastat_service
from main_bot.utils.session_manager import SessionManager
from instance_bot import bot

logger = logging.getLogger(__name__)

async def update_channel_stats(channel_id: int):
    """
    Ежечасная задача по обновлению статистики канала и постов.
    """
    logger.info(f"Starting hourly stats update for channel {channel_id}")
    
    # 1. Получаем канал и проверяем подписку
    channel = await db.get_channel_by_chat_id(channel_id)
    if not channel:
        logger.warning(f"Channel {channel_id} not found during stats update")
        return

    # Проверка подписки (если есть поле subscribe? В модели видел Optional[int])
    if not channel.subscribe or channel.subscribe < int(time.time()):
        logger.info(f"Channel {channel.title} ({channel.chat_id}) has no active subscription. Skipping update.")
        return

    # 2. Инициализируем клиент (Internal)
    # Ищем клиент, привязанный к каналу (preferred_for_stats или любой активный админа?)
    # Обычно используем того, через кого постим, или специального.
    # В models.py Channel есть admin_id.
    # Попробуем найти клиент через get_preferred_for_stats или просто get_active_client_for_channel?
    # В utils/novastat мы искали get_preferred_for_stats.
    
    mt_client_channel = await db.get_preferred_for_stats(channel.chat_id)
    client_obj = None
    
    if mt_client_channel:
        client_obj = await db.get_mt_client(mt_client_channel.client_id)
        
    if not client_obj:
        # Fallback: try to find any client for this admin? or just fail?
        # User implies we "make request with client".
        logger.warning(f"No MTClient found for channel {channel.title}. Skipping.")
        return

    session_path = client_obj.session_path
    manager = SessionManager(session_path)
    await manager.init_client()
    
    if not manager.client:
        logger.error(f"Failed to init client {client_obj.id}")
        return

    try:
        client = manager.client
        
        # Получаем entity канала
        try:
            entity = await client.get_entity(channel.chat_id)
        except Exception as e:
            logger.error(f"Failed to get entity for {channel.chat_id}: {e}")
            return

        # 3. Обновляем подписчиков
        try:
            full = await client(functions.channels.GetFullChannelRequest(channel=entity))
            subs = int(getattr(full.full_chat, "participants_count", 0) or 0)
            
            # Обновляем в БД
            await db.update_channel(channel.id, subscribers_count=subs)
            logger.info(f"Updated subscribers for {channel.title}: {subs}")
        except Exception as e:
            logger.error(f"Failed to get subscribers: {e}")

        # 4. Обновляем NovaStat данные (24/48/72)
        # Используем существующую логику сбора (она вернет dict с views/er)
        # days_limit=4 (достаточно для 72ч)
        try:
            stats = await novastat_service._collect_stats_impl(client, entity, days_limit=4)
            if stats and 'views' in stats:
                views_data = stats['views'] # {24: ..., 48: ..., 72: ...}
                
                await db.update_channel(
                    channel.id,
                    novastat_24h=views_data.get(24, 0),
                    novastat_48h=views_data.get(48, 0),
                    novastat_72h=views_data.get(72, 0)
                )
                logger.info(f"Updated NovaStat cache for {channel.title}")
        except Exception as e:
            logger.error(f"Failed to collect NovaStat: {e}")

        # 5. Обновляем просмотры постов (< 72ч)
        current_time = int(time.time())
        limit_time = current_time - (72 * 3600 + 600) # + reserve
        
        # Нужно добавить метод получения активных постов канала свежее X
        # В PublishedPostCrud: select ... where chat_id=... status='active' created > limit
        # Пока используем get_published_posts_by_channel_recent (надо добавить или через session select)
        
        # Так как Crud не имеет такого метода, добавлю его "на лету" или расширю crud позже.
        # Пока сделаю через session selection здесь, если db.session доступна, но db.fetch лучше.
        
        # Импорт модели нужен для запроса
        from main_bot.database.published_post.model import PublishedPost
        from sqlalchemy import select, and_

        query = select(PublishedPost).where(
            and_(
                PublishedPost.chat_id == channel.chat_id,
                PublishedPost.status == 'active',
                PublishedPost.created_timestamp > limit_time
            )
        )
        
        recent_posts = await db.fetch(query)
        
        if not recent_posts:
            logger.info("No recent posts to update.")
            return

        # Собираем message_ids
        msg_ids = [p.message_id for p in recent_posts]
        
        # Запрашиваем сообщения пачкой
        try:
            messages = await client.get_messages(entity, ids=msg_ids)
            
            for msg in messages:
                if not msg or not isinstance(msg, types.Message):
                    continue
                
                # Находим соответствующий пост в БД
                post_obj = next((p for p in recent_posts if p.message_id == msg.id), None)
                if not post_obj:
                    continue
                
                views = int(msg.views or 0)
                age_seconds = current_time - post_obj.created_timestamp
                age_hours = age_seconds / 3600.0
                
                update_data = {}
                
                if age_hours <= 24:
                    update_data['views_24h'] = views
                elif age_hours <= 48:
                    update_data['views_48h'] = views
                elif age_hours <= 72:
                    update_data['views_72h'] = views
                
                if update_data:
                    await db.update_published_post(post_obj.id, **update_data)
                    
            logger.info(f"Updated views for {len(messages)} posts in {channel.title}")
            
        except Exception as e:
            logger.error(f"Failed to update post views: {e}")

    finally:
        await manager.close()


def schedule_channel_job(scheduler: AsyncIOScheduler, channel):
    """
    Планирует задачу для канала.
    Запуск раз в час в минуту добавления канала.
    """
    # Вычисляем минуту запуска
    # Используем created_timestamp
    created_dt = datetime.fromtimestamp(channel.created_timestamp)
    minute = created_dt.minute
    second = created_dt.second
    
    job_id = f"channel_stats_{channel.chat_id}"
    
    scheduler.add_job(
        func=update_channel_stats,
        trigger=CronTrigger(minute=minute, second=second),
        id=job_id,
        args=[channel.chat_id],
        replace_existing=True,
        name=f"Stats update for {channel.title}"
    )
    logger.info(f"Scheduled stats job for {channel.title} at XX:{minute:02d}:{second:02d}")


async def register_channel_jobs(scheduler: AsyncIOScheduler):
    """
    Регистрирует задачи для всех каналов при старте.
    """
    channels = await db.get_channels()
    for channel in channels:
        schedule_channel_job(scheduler, channel)
