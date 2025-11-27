import asyncio
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from typing import List, Tuple, Dict, Optional

from telethon import TelegramClient
from telethon.tl import functions, types
from telethon.errors import RPCError
from config import Config

# Constants
TIMEZONE = "Europe/Moscow"
HORIZONS = [24, 48, 72]
ANOMALY_FACTOR = 10

class NovaStatService:
    def __init__(self, session_path: str = "main_bot/utils/sessions/+37253850093"):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH
        self.session_path = session_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)

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
import asyncio
import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from typing import List, Tuple, Dict, Optional

from telethon import TelegramClient
from telethon.tl import functions, types
from telethon.errors import RPCError
from config import Config

# Constants
TIMEZONE = "Europe/Moscow"
HORIZONS = [24, 48, 72]
ANOMALY_FACTOR = 10

class NovaStatService:
    def __init__(self, session_path: str = "main_bot/utils/sessions/+37253850093"):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH
        self.session_path = session_path
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.session_path), exist_ok=True)

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

    def get_client(self) -> TelegramClient:
        return TelegramClient(self.session_path, self.api_id, self.api_hash)

    async def check_access(self, channel_identifier: str, client: TelegramClient = None) -> Optional[types.TypeInputPeer]:
        """
        Checks access to the channel and returns the entity if successful.
        Returns None if access failed.
        """
        if client:
            return await self._check_access_impl(client, channel_identifier)
        
        async with self.get_client() as new_client:
            return await self._check_access_impl(new_client, channel_identifier)

    async def _check_access_impl(self, client: TelegramClient, channel_identifier: str) -> Optional[types.TypeInputPeer]:
        entity = None
        # 3 attempts to get entity
        for attempt in range(3):
            try:
                if "+" in channel_identifier and "t.me" in channel_identifier:
                    hash_part = channel_identifier.split("+", 1)[1]
                    try:
                        res = await client(functions.messages.ImportChatInviteRequest(hash=hash_part))
                        entity = res.chats[0]
                    except Exception:
                            # Maybe already joined or public link disguised
                            entity = await client.get_entity(channel_identifier)
                else:
                    entity = await client.get_entity(channel_identifier)
                
                if entity:
                    break
            except Exception as e:
                print(f"Attempt {attempt+1} failed for {channel_identifier}: {e}")
                if attempt < 2:
                    await asyncio.sleep(1 + attempt) # 1s then 2s
        
        return entity

    async def collect_stats(self, channel_identifier: str, days_limit: int = 7, client: TelegramClient = None) -> Optional[Dict]:
        """
        Collects stats for a channel. 
        """
        if client:
            return await self._collect_stats_impl(client, channel_identifier, days_limit)

        async with self.get_client() as new_client:
            return await self._collect_stats_impl(new_client, channel_identifier, days_limit)

    async def _collect_stats_impl(self, client: TelegramClient, channel_identifier: str, days_limit: int) -> Optional[Dict]:
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
