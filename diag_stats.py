import asyncio
import os
import sys

# Добавляем путь к проекту
sys.path.append(os.getcwd())

from main_bot.database.db import db
from sqlalchemy import select
from main_bot.database.channel.model import Channel
from main_bot.database.mt_client_channel.model import MtClientChannel
from main_bot.database.novastat_cache.model import NovaStatCache

async def check():
    async with db.engine.connect() as conn:
        # 1. Последние добавленные каналы
        print("--- Последние 10 каналов ---")
        stmt = select(Channel).order_by(Channel.created_timestamp.desc()).limit(10)
        res = await db.fetch(stmt)
        for ch in res:
            print(f"ID: {ch.chat_id} | Title: {ch.title} | Subs: {ch.subscribers_count} | 24h: {ch.novastat_24h} | Created: {ch.created_timestamp}")
            
        # 2. Проверка привязки клиентов
        print("\n--- Привязка клиентов для этих каналов ---")
        for ch in res:
            stmt = select(MtClientChannel).where(MtClientChannel.channel_id == ch.chat_id)
            links = await db.fetch(stmt)
            for l in links:
                print(f"Channel: {l.channel_id} | Client: {l.client_id} | Preferred Stats: {l.preferred_for_stats} | Member: {l.is_member}")
        
        # 3. Кэш NovaStat
        print("\n--- Кэш NovaStat (последние записи) ---")
        stmt = select(NovaStatCache).order_by(NovaStatCache.updated_at.desc()).limit(10)
        cache_res = await db.fetch(stmt)
        for c in cache_res:
            print(f"ID: {c.channel_identifier} | Horizon: {c.horizon} | Updated: {c.updated_at} | InProgress: {c.refresh_in_progress}")

if __name__ == "__main__":
    asyncio.run(check())
