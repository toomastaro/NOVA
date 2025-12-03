import asyncio
import os
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from telethon import TelegramClient
from telethon.tl import functions, types
from telethon.errors import RPCError
from config import Config

from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

# Constants
TIMEZONE = "Europe/Moscow"
HORIZONS = [24, 48]
ANOMALY_FACTOR = 10
CACHE_TTL_SECONDS = 3600  # 60 минут

class NovaStatService:
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    def human_dt(self, dt_utc: datetime, tz: ZoneInfo) -> str:
        return dt_utc.astimezone(tz).strftime("%d.%m.%Y %H:%M")

    def interpolate_by_age(self, target_age: float, points: List[Tuple[float, int]]) -> int:
        if not points:
            return 0
        pts = sorted(points, key=lambda x: x[0])
        if len(pts) == 1:
            return int(pts[0][1])
        if target_age <= pts[0][0]:
            return int(pts[0][1])
        if target_age >= pts[-1][0]:
            return int(pts[-1][1])

        prev_age, prev_views = pts[0]
        for age, views in pts[1:]:
            if age == target_age:
                return int(views)
            if age > target_age:
                total = age - prev_age
                if total <= 0:
                    return int(prev_views)
                ratio = (target_age - prev_age) / total
                est = prev_views + (views - prev_views) * ratio
                return int(round(est))
            prev_age, prev_views = age, views
        return int(pts[-1][1])

    async def get_external_client(self) -> Optional[tuple]:
        """Получить активного external MtClient и SessionManager"""
        clients = await db.get_mt_clients_by_pool('external')
        active_clients = [c for c in clients if c.is_active and c.status == 'ACTIVE']
        
        if not active_clients:
            return None
        
        # Выбрать первого активного клиента
        client = active_clients[0]
        session_path = Path(client.session_path)
        
        if not session_path.exists():
            return None
        
        manager = SessionManager(session_path)
        await manager.init_client()
        
        if not manager.client:
            return None
        
        return (client, manager)

    async def collect_stats(self, channel_identifier: str, days_limit: int = 7, horizon: int = 24) -> Optional[Dict]:
        """
        Собрать статистику для канала с кэшированием.
        
        Args:
            channel_identifier: username или ссылка на канал
            days_limit: глубина анализа в днях
            horizon: горизонт для кэша (24, 48, 72)
        
        Returns:
            Dict со статистикой или None при ошибке
        """
        # 1. Проверить кэш
        is_fresh = await db.is_cache_fresh(channel_identifier, horizon, CACHE_TTL_SECONDS)
        
        if is_fresh:
            cache = await db.get_cache(channel_identifier, horizon)
            if cache and not cache.error_message:
                return cache.value_json
        
        # 2. Проверить, идет ли обновление
        cache = await db.get_cache(channel_identifier, horizon)
        if cache and cache.refresh_in_progress:
            # Вернуть старые данные или None
            if cache.value_json:
                return cache.value_json
            return None
        
        # 3. Запустить асинхронное обновление
        asyncio.create_task(self.async_refresh_stats(channel_identifier, days_limit, horizon))
        
        # 4. Вернуть старые данные если есть
        if cache and cache.value_json:
            return cache.value_json
        
        return None

    async def async_refresh_stats(self, channel_identifier: str, days_limit: int, horizon: int):
        """Асинхронное обновление статистики в кэше"""
        try:
            # Установить флаг обновления
            await db.mark_refresh_in_progress(channel_identifier, horizon, True)
            
            # Получить external клиента
            client_data = await self.get_external_client()
            if not client_data:
                await db.set_cache(
                    channel_identifier,
                    horizon,
                    {},
                    error_message="Нет доступных external клиентов"
                )
                return
            
            client_obj, manager = client_data
            
            try:
                # Собрать статистику
                stats = await self._collect_stats_impl(manager.client, channel_identifier, days_limit)
                
                if stats:
                    # Сохранить в кэш
                    await db.set_cache(channel_identifier, horizon, stats, error_message=None)
                else:
                    await db.set_cache(
                        channel_identifier,
                        horizon,
                        {},
                        error_message="Не удалось собрать статистику"
                    )
            finally:
                await manager.close()
                
        except Exception as e:
            error_msg = str(e)
            
            # Обработать специфичные ошибки
            if "USER_NOT_PARTICIPANT" in error_msg or "CHAT_ADMIN_REQUIRED" in error_msg:
                error_msg = "Канал недоступен: бот не участник"
            elif "CHANNEL_PRIVATE" in error_msg:
                error_msg = "Канал приватный"
            
            await db.set_cache(
                channel_identifier,
                horizon,
                {},
                error_message=error_msg
            )
        finally:
            # Сбросить флаг обновления
            await db.mark_refresh_in_progress(channel_identifier, horizon, False)

    async def _collect_stats_impl(self, client: TelegramClient, channel_identifier: str, days_limit: int) -> Optional[Dict]:
        """Внутренняя реализация сбора статистики"""
        tz = ZoneInfo(TIMEZONE)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)

        try:
            entity = await client.get_entity(channel_identifier)
        except Exception:
            return None

        title = getattr(entity, "title", getattr(entity, "username", str(entity)))
        username = getattr(entity, "username", None)
        
        # Get subscribers
        try:
            full = await client(functions.channels.GetFullChannelRequest(channel=entity))
            members = int(getattr(full.full_chat, "participants_count", 0) or 0)
        except RPCError:
            members = 0

        # Get posts
        cutoff_utc = now_utc - timedelta(days=days_limit)
        raw_points: List[Tuple[float, int]] = []

        async for m in client.iter_messages(entity, offset_date=cutoff_utc, reverse=True):
            if not isinstance(m, types.Message):
                continue
            if not m.date or m.views is None:
                continue

            msg_dt_utc = m.date.replace(tzinfo=timezone.utc)
            if msg_dt_utc < cutoff_utc:
                continue

            age_hours = (now_utc - msg_dt_utc).total_seconds() / 3600.0
            views = int(m.views)
            raw_points.append((age_hours, views))

        # Determine link
        link = None
        if username:
            link = f"https://t.me/{username}"
        elif "t.me" in channel_identifier:
            link = channel_identifier

        if not raw_points:
            # No posts or views found, return 0 stats
            return {
                'title': title,
                'username': username,
                'link': link,
                'subscribers': members,
                'views': {24: 0, 48: 0, 72: 0},
                'er': {24: 0.0, 48: 0.0, 72: 0.0}
            }

        # Filter anomalies
        views_list = [v for (_, v) in raw_points]
        med = int(median(views_list))
        threshold = med * ANOMALY_FACTOR if med > 0 else None

        if threshold:
            valid_points = [(age, v) for (age, v) in raw_points if v <= threshold]
        else:
            valid_points = raw_points

        if not valid_points:
                return {
                'title': title,
                'username': username,
                'link': link,
                'subscribers': members,
                'views': {24: 0, 48: 0, 72: 0},
                'er': {24: 0.0, 48: 0.0, 72: 0.0}
            }

        # Interpolate
        views_res = {}
        er_res = {}
        for h in HORIZONS:
            val = self.interpolate_by_age(float(h), valid_points)
            views_res[h] = val
            if members > 0:
                er_res[h] = round((val / members) * 100, 2)
            else:
                er_res[h] = 0.0

        return {
            'title': title,
            'username': username,
            'link': link,
            'subscribers': members,
            'views': views_res,
            'er': er_res
        }

novastat_service = NovaStatService()

