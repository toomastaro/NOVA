import asyncio
import logging
import time
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, and_
from telethon.tl import functions, types

from main_bot.database.db import db
from main_bot.database.published_post.model import PublishedPost
from main_bot.utils.novastat import novastat_service
from main_bot.utils.session_manager import SessionManager
from instance_bot import bot

logger = logging.getLogger(__name__)


async def update_channel_stats(channel_id: int):
    """
    Ежечасная задача по обновлению статистики канала и постов.
    """
    logger.info(f"Запуск ежечасного обновления статистики для канала {channel_id}")
    
    # 1. Получаем канал и проверяем подписку
    channel = await db.channel.get_channel_by_chat_id(channel_id)
    if not channel:
        logger.warning(f"Канал {channel_id} не найден во время обновления статистики")
        return

    # Проверка подписки
    if not channel.subscribe or channel.subscribe < int(time.time()):
        logger.info(f"Канал {channel.title} ({channel.chat_id}) не имеет активной подписки. Пропуск обновления.")
        return

    # 2. Инициализируем клиент (Internal)
    # Ищем клиент, привязанный к каналу (preferred_for_stats или любой активный)
    mt_client_channel = await db.mt_client_channel.get_preferred_for_stats(channel.chat_id)
    
    if not mt_client_channel:
        # Fallback: берем любого привязанного клиента
        mt_client_channel = await db.mt_client_channel.get_any_client_for_channel(channel.chat_id)
        if mt_client_channel:
            logger.info(f"Используется fallback клиент {mt_client_channel.client_id} для канала {channel.title}")
            
    client_obj = None
    
    if mt_client_channel:
        client_obj = await db.mt_client.get_mt_client(mt_client_channel.client_id)
        
    if not client_obj:
        logger.warning(f"MTClient не найден для канала {channel.title}. Пропуск.")
        return

    session_path = client_obj.session_path
    
    # Используем SessionManager как контекстный менеджер, чтобы гарантировать закрытие
    # Но здесь логика сложнее, так как manager.init_client() вызывается явно
    # Лучше использовать async with SessionManager(...) as manager:
    # Но нужно убедиться, что session_path это Path или строка, SessionManager принимает Path (обычно)
    # Проверим тип в SessionManager. Он импортирован из utils.
    # Обычно он принимает Path.
    
    from pathlib import Path
    path_obj = Path(session_path)

    async with SessionManager(path_obj) as manager:
        if not manager.client or not await manager.client.is_user_authorized():
            logger.error(f"Не удалось инициализировать клиент {client_obj.id}")
            return

        client = manager.client
        
        # Получаем entity канала
        try:
            entity = await client.get_entity(channel.chat_id)
        except Exception as e:
            logger.error(f"Не удалось получить entity для {channel.chat_id}: {e}")
            return

        # 3. Обновляем подписчиков
        try:
            full = await client(functions.channels.GetFullChannelRequest(channel=entity))
            subs = int(getattr(full.full_chat, "participants_count", 0) or 0)
            
            # Обновляем в БД
            await db.channel.update_channel_by_id(channel.id, subscribers_count=subs)
            logger.info(f"Обновлены подписчики для {channel.title}: {subs}")
        except Exception as e:
            logger.error(f"Не удалось получить подписчиков: {e}")

        # 4. Обновляем NovaStat данные (24/48/72)
        # days_limit=4 (достаточно для 72ч)
        try:
            stats = await novastat_service._collect_stats_impl(client, entity, days_limit=4)
            if stats and 'views' in stats:
                views_data = stats['views'] # {24: ..., 48: ..., 72: ...}
                
                await db.channel.update_channel_by_id(
                    channel.id,
                    novastat_24h=views_data.get(24, 0),
                    novastat_48h=views_data.get(48, 0),
                    novastat_72h=views_data.get(72, 0)
                )
                logger.info(f"Обновлен кэш NovaStat для {channel.title}")
        except Exception as e:
            logger.error(f"Не удалось собрать NovaStat: {e}")

        # 5. Обновляем просмотры постов (< 72ч)
        current_time = int(time.time())
        limit_time = current_time - (72 * 3600 + 600) # + reserve
        
        query = select(PublishedPost).where(
            and_(
                PublishedPost.chat_id == channel.chat_id,
                PublishedPost.status == 'active',
                PublishedPost.created_timestamp > limit_time
            )
        )
        
        recent_posts = await db.fetch_all(query)
        if not recent_posts:
            # Преобразуем scalar result если надо, или fetch_all вернет список
            recent_posts = []

        # Если db.fetch_all возвращает строки, нужно их маппить?
        # Предполагаем, что ORM возвращает объекты PublishedPost.
        # Если нет постов, выходим
        if not recent_posts:
            logger.info("Нет недавних постов для обновления.")
            return

        # Собираем message_ids
        # Проверка типа: если это Scalar object, attributes доступны.
        msg_ids = [p.message_id for p in recent_posts if hasattr(p, 'message_id')]
        
        if not msg_ids:
            return

        # Запрашиваем сообщения пачкой
        try:
            messages = await client.get_messages(entity, ids=msg_ids)
            
            updated_count = 0
            for msg in messages:
                if not msg or not isinstance(msg, types.Message):
                    continue
                
                # Находим соответствующий пост в БД
                post_obj = next((p for p in recent_posts if p.message_id == msg.id), None)
                if not post_obj:
                    continue
                
                # views мб None
                views = int(getattr(msg, 'views', 0) or 0)
                
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
                    await db.published_post.update_published_post(post_obj.id, **update_data)
                    updated_count += 1
                    
            logger.info(f"Обновлены просмотры для {updated_count} постов в {channel.title}")
            
        except Exception as e:
            logger.error(f"Не удалось обновить просмотры постов: {e}")


def schedule_channel_job(scheduler: AsyncIOScheduler, channel):
    """
    Планирует задачу для канала.
    Запуск раз в час в минуту добавления канала.
    """
    # Вычисляем минуту запуска
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
        name=f"Обновление статистики для {channel.title}"
    )
    logger.info(f"Запланирована задача статистики для {channel.title} в XX:{minute:02d}:{second:02d}")


async def register_channel_jobs(scheduler: AsyncIOScheduler):
    """
    Регистрирует задачи для всех каналов при старте.
    """
    channels = await db.channel.get_channels()
    for channel in channels:
        schedule_channel_job(scheduler, channel)
