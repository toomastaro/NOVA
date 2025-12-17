"""
Планировщик сбора статистики рекламы.

Этот модуль отслеживает вступления и выходы пользователей по пригласительным ссылкам
для активных рекламных кампаний, используя Admin Log каналов.
"""
import asyncio
import logging
import time
from pathlib import Path
from typing import List

from sqlalchemy import select, update
from telethon.tl.types import (
    ChannelAdminLogEventActionParticipantJoinByInvite,
    ChannelAdminLogEventActionParticipantLeave,
)

from config import Config
from main_bot.database.db import db
from main_bot.database.channel.model import Channel
from main_bot.database.ad_purchase.model import AdPurchase, AdPurchaseLinkMapping
from main_bot.database.db_types import AdTargetType
from main_bot.utils.session_manager import SessionManager

logger = logging.getLogger(__name__)


async def ad_stats_worker() -> None:
    """
    DEPRECATED: Этот воркер больше не используется, так как APScheduler управляет интервалами.
    Используйте process_ad_stats() напрямую.
    """
    interval = Config.zakup_timer or 600
    logger.info(f"Ad Stats Worker запущен с интервалом {interval}с")

    while True:
        try:
            await process_ad_stats()
        except Exception as e:
            logger.error(f"Ошибка в ad_stats_worker: {e}", exc_info=True)

        await asyncio.sleep(interval)


async def process_ad_stats() -> None:
    """
    Основная логика сбора статистики рекламы.
    Сканирует админ-логи для активных закупок рекламы.
    """
    current_time = int(time.time())

    # 1. Находим пользователей, у которых есть хотя бы одна активная платная подписка на канал
    # Запрашиваем Channels напрямую
    query = select(Channel.admin_id).where(
        Channel.subscribe > current_time
    ).distinct()

    paid_admin_ids = await db.fetch(query)
    # db.fetch для одного поля возвращает список значений (scalars)
    admin_ids = list(paid_admin_ids) if paid_admin_ids else []

    if not admin_ids:
        return

    logger.info(f"Сканирование статистики рекламы для {len(admin_ids)} платных админов")

    # 2. Для этих админов находим АКТИВНЫЕ закупки рекламы (Ad Purchases)
    query = select(AdPurchase).where(
        AdPurchase.owner_id.in_(admin_ids),
        AdPurchase.status == "active"
    )
    active_purchases = await db.fetch_all(query)

    if not active_purchases:
        return

    # 3. Для каждой закупки получаем привязки (mappings)
    for purchase in active_purchases:
        mappings = await db.ad_purchase.get_link_mappings(purchase.id)

        # Группируем привязки по каналу, чтобы минимизировать вызовы getAdminLog
        # Нас интересует только тип цели CHANNEL, где включено отслеживание
        channel_mappings = {} # {channel_id: [mappings]}

        for m in mappings:
            if m.target_type == AdTargetType.CHANNEL and m.track_enabled and m.target_channel_id:
                if m.target_channel_id not in channel_mappings:
                    channel_mappings[m.target_channel_id] = []
                channel_mappings[m.target_channel_id].append(m)

        # Обрабатываем каждый канал
        for channel_id, maps in channel_mappings.items():
            await process_channel_logs(channel_id, maps)


async def process_channel_logs(channel_id: int, mappings: List[AdPurchaseLinkMapping]) -> None:
    """
    Получает и обрабатывает админ-логи для конкретного канала и сверяет с привязками.

    Аргументы:
        channel_id (int): ID канала для сканирования.
        mappings (List[AdPurchaseLinkMapping]): Список привязок ссылок для этого канала.
    """
    client_model = await db.mt_client_channel.get_preferred_for_stats(channel_id)
    if not client_model:
        client_model = await db.mt_client_channel.get_any_client_for_channel(channel_id)

    if not client_model or not client_model.client:
        return

    session_path = Path(client_model.client.session_path)
    if not session_path.exists():
        logger.warning(f"Файл сессии не найден для клиента {client_model.client.id}: {session_path}")
        return

    async with SessionManager(session_path) as manager:
        try:
             # Инициализация если не выполнена
            if not manager.client:
                 await manager.init_client()

            if not manager.client or not await manager.client.is_user_authorized():
                logger.warning(f"Не удалось загрузить сессию для клиента {client_model.id} или нет авторизации")
                return

            client = manager.client

            min_scanned_id = min((m.last_scanned_id for m in mappings), default=0)

            try:
                # Telethon: iter_admin_log
                # Нам нужны события вступления и выхода
                async for event in client.iter_admin_log(
                    entity=channel_id,
                    limit=None,
                    min_id=min_scanned_id,
                    join=True,
                    leave=True,
                    invite=True
                ):
                    event_id = event.id
                    user_id = event.user_id

                    # --- JOIN BY INVITE ---
                    if isinstance(event.action, ChannelAdminLogEventActionParticipantJoinByInvite):
                        invite_link = event.action.invite.link

                        if invite_link:
                            def normalize_link(link: str) -> str:
                                if not link:
                                    return ""
                                return link.replace("https://", "").replace("http://", "").replace("t.me/", "").replace("telegram.me/", "").replace("+", "").strip()

                            norm_event_link = normalize_link(invite_link)

                            # Проверяем, принадлежит ли эта ссылка какой-либо привязке
                            for m in mappings:
                                if normalize_link(m.invite_link) == norm_event_link:
                                    await db.ad_purchase.process_join_event(
                                        channel_id=channel_id,
                                        user_id=user_id,
                                        invite_link=m.invite_link # Используем ссылку из БД для согласованности
                                    )
                                    logger.info(f"Обработан JOIN через AdminLog: Пользователь {user_id} -> Закупка {m.ad_purchase_id}")

                    # --- LEAVE EVENT ---
                    elif isinstance(event.action, ChannelAdminLogEventActionParticipantLeave):
                        # update_subscription_status обрабатывает логику по (user_id, channel_id)
                        await db.ad_purchase.update_subscription_status(
                            user_id=user_id,
                            channel_id=channel_id,
                            status="left"
                        )
                        logger.info(f"Обработан LEAVE через AdminLog: Пользователь {user_id} в канале {channel_id}")


                    # Обновляем максимальный сканированный ID для ВСЕХ привязок этого канала
                    # Это немного неточно, если событий много и мы упадем посередине, но приемлемо
                    for m in mappings:
                        if event_id > m.last_scanned_id:
                             q = update(AdPurchaseLinkMapping).where(AdPurchaseLinkMapping.id == m.id).values(last_scanned_id=event_id)
                             await db.execute(q)
                             m.last_scanned_id = event_id

            except Exception as e:
                logger.error(f"Ошибка получения админ-лога для канала {channel_id}: {e}")

        except Exception as e:
             logger.error(f"Ошибка инициализации клиента в ad_stats: {e}")
