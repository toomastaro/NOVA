import asyncio
import logging
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from aiogram import Bot
from telethon import TelegramClient, utils
from sqlalchemy import select
from main_bot.database.mt_client.model import MtClient
from telethon.tl import functions, types
from telethon.errors import RPCError
from config import Config

from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager
from main_bot.utils.redis_client import redis_client
import json

logger = logging.getLogger(__name__)

# Константы
TIMEZONE = "Europe/Moscow"
HORIZONS = [24, 48, 72]
ANOMALY_FACTOR = 10
CACHE_TTL_SECONDS = 10800


class NovaStatService:
    def __init__(self):
        self.api_id = Config.API_ID
        self.api_hash = Config.API_HASH

    def human_dt(self, dt_utc: datetime, tz: ZoneInfo) -> str:
        return dt_utc.astimezone(tz).strftime("%d.%m.%Y %H:%M")

    def interpolate_by_age(
        self, target_age: float, points: List[Tuple[float, int]]
    ) -> int:
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

    async def get_external_client(self, preferred_client_id: int = None) -> Optional[tuple]:
        """
        Получить внешнего клиента. 
        Сначала пробуем preferred_client_id (если передан).
        Иначе берем наименее используемого.
        """
        
        # 1. Сначала пробуем "липкого" клиента
        preferred_client = None
        if preferred_client_id:
            preferred_client = await db.mt_client.get_mt_client(preferred_client_id)
            if preferred_client and (not preferred_client.is_active or preferred_client.status != "ACTIVE"):
                preferred_client = None # Он уже не активен

        # 2. Получаем список всех активных внешних клиентов
        clients = await db.mt_client.fetch(
            select(MtClient)
            .where(MtClient.pool_type == "external")
            .where(MtClient.is_active)
            .where(MtClient.status == "ACTIVE")
            .order_by(MtClient.usage_count.asc(), MtClient.last_used_at.asc())
        )

        if not clients:
            logger.warning("Нет активных внешних клиентов")
            return None

        # Если есть preferred и он есть в списке (или просто активен), ставим его первым
        # Но clients - это список из БД.
        # Просто переупорядочим список: preferred первым
        if preferred_client:
            # Проверяем, есть ли он в clients (вдруг pool_type сменился)
            # Если он валиден для пула external, он будет в clients?
            # Лучше просто найти его в clients и перенести в начало
            
            # Находим индекс
            idx = -1
            for i, c in enumerate(clients):
                if c.id == preferred_client.id:
                    idx = i
                    break
            
            if idx != -1:
                # Переносим в начало
                p = clients.pop(idx)
                clients.insert(0, p)
                logger.info(f"🎯 Приоритетное использование клиента {p.alias} ({p.id})")
            else:
                logger.warning(f"Preferred client {preferred_client.id} не найден среди активных external-клиентов.")


        if not clients:
            logger.warning("Нет активных внешних клиентов")
            return None

        for client in clients:
            logger.debug(
                f"🔄 Проверка внешнего клиента {client.id} ({client.alias}) с использованием={client.usage_count}"
            )

            session_path = Path(client.session_path)
            if not session_path.exists():
                logger.error(
                    f"Файл сессии не найден для внешнего клиента {client.id}: {session_path}"
                )
                continue

            manager = SessionManager(session_path)
            await manager.init_client()

            if not manager.client:
                logger.error(
                    f"Не удалось инициализировать клиент для внешнего клиента {client.id}"
                )
                await manager.close()
                continue

            # Проверка авторизации
            try:
                if not await manager.client.is_user_authorized():
                    logger.error(f"Клиент {client.id} ({client.alias}) не авторизован! Деактивация.")
                    await db.mt_client.update_mt_client(client.id, is_active=False, status="UNAUTHORIZED")
                    await manager.close()
                    continue
            except Exception as e:
                logger.error(f"Ошибка проверки авторизации клиента {client.id}: {e}")
                await manager.close()
                continue

            # Увеличить счетчик использования
            await db.mt_client.increment_usage(client.id)
            logger.debug(f"Выбран клиент {client.id}, счетчик использования увеличен")

            return (client, manager)

        logger.error("Все внешние клиенты не прошли проверку авторизации или инициализации")
        return None

    def normalize_identifier(self, identifier: str) -> str:
        """
        Нормализует идентификатор канала.
        Убирает @, t.me/, пробелы и приводит к нижнему регистру.
        Если это приватная ссылка, возвращает её целиком.
        """
        if not identifier:
            return ""
        
        s = str(identifier).strip()
        
        # 0. Если это команда, считаем её недопустимым идентификатором канала
        if s.startswith("/"):
            return ""

        # 0.1 ОПРЕДЕЛЕНИЕ: Ссылки-приглашения (t.me/+) ЧУВСТВИТЕЛЬНЫ К РЕГИСТРУ
        # Если это ссылка или юзернейм с регистром, мы должны быть осторожны.
        # Но Telegram USERNAME всегда нечувствительны к регистру в поиске.
        # А вот Private Join Links - чувствительны.
        is_sensitive = "t.me/+" in s or "joinchat/" in s
        
        if not is_sensitive:
            s = s.lower()
        if s.lstrip("-").isdigit():
            return s
            
        # 2. Обработка ссылок t.me
        if "t.me/" in s:
            # Убираем параметры запроса (?start=...) и якоря
            s = s.split("?")[0].split("#")[0]
            # Убираем слеш в конце
            s = s.rstrip("/")
            
            # Если это приватная ссылка, возвращаем её целиком для ImportChatInvite
            if "t.me/+" in s or "joinchat/" in s:
                return s
            
            # Берем последний сегмент (username)
            parts = s.split("/")
            if parts[-1]:
                s = parts[-1]
            elif len(parts) > 1:
                s = parts[-2]
            
        # 3. Базовая очистка
        s = s.replace("@", "").strip()
        
        return s

    def normalize_cache_keys(self, data: Optional[Dict]) -> Optional[Dict]:
        """Преобразовать строковые ключи из JSON обратно в числовые"""
        if not data:
            return data

        # Создать копию данных
        normalized = data.copy()

        # Преобразовать ключи в views и er
        if "views" in normalized and isinstance(normalized["views"], dict):
            normalized["views"] = {int(k): v for k, v in normalized["views"].items()}

        if "er" in normalized and isinstance(normalized["er"], dict):
            normalized["er"] = {int(k): v for k, v in normalized["er"].items()}

        return normalized

    async def collect_stats(
        self,
        channel_identifier: str,
        days_limit: int = 7,
        horizon: int = 24,
        bot: Bot = None,
    ) -> Optional[Dict]:
        """
        Собрать статистику для канала с кэшированием и учетом ExternalChannel.
        """
        # 0. Валидация ввода
        if not channel_identifier or not str(channel_identifier).strip():
            return None
        
        id_str = str(channel_identifier).strip()
        clean_id = self.normalize_identifier(id_str)
        
        if not clean_id:
            logger.warning(f"Недопустимый формат идентификатора канала: {id_str}")
            return {"error": "Некорректный формат (команды и пустой текст не поддерживаются)"}
        
        # 1. Поиск chat_id
        chat_id = None
        # Проверяем, не числовой ли это ID
        if clean_id.lstrip("-").isdigit():
            chat_id = int(clean_id)
        else:
            # Сначала проверяем "свои" каналы по названию
            our_ch = await db.channel.get_channel_by_title(clean_id)
            if our_ch:
                chat_id = our_ch.chat_id
            
            # Если не нашли в своих, ищем во внешних
            if not chat_id:
                ext_ch = await db.external_channel.get_by_username(clean_id)
                if not ext_ch and ("t.me/+" in clean_id or "joinchat/" in clean_id):
                    ext_ch = await db.external_channel.get_by_link(clean_id)
                
                if ext_ch:
                    chat_id = ext_ch.chat_id

        # Ключ для таблицы кэша (предпочтительно chat_id, если он есть)
        cache_key_suffix = str(chat_id) if chat_id else clean_id
        redis_data_key = f"novastat:data:{cache_key_suffix}:{horizon}"
        logger.info(f"📊 [NovaStat] Запрос статистики: identifier={id_str}, clean_id={clean_id}, chat_id={chat_id}, redis_key={redis_data_key}")

        # --- FAST PATH FOR INTERNAL CHANNELS ---
        # Если канал является внутренним, мы возвращаем данные напрямую из БД каналов,
        # минуя redis и MTProto.
        if chat_id:
            logger.debug(f"🔍 [NovaStat] Проверка внутреннего канала для chat_id={chat_id}")
            our_channel_fresh = await db.channel.get_channel_by_chat_id(chat_id)
            if our_channel_fresh:
                logger.info(f"⚡ [Fast Path] Канал {clean_id} (chat_id={chat_id}) - ВНУТРЕННИЙ. Возврат данных из БД channels.")
                subs = our_channel_fresh.subscribers_count
                views_res = {
                    24: our_channel_fresh.novastat_24h,
                    48: our_channel_fresh.novastat_48h,
                    72: our_channel_fresh.novastat_72h,
                }
                er_res = {}
                for h in [24, 48, 72]:
                    if subs > 0:
                        er_res[h] = round((views_res[h] / subs) * 100, 2)
                    else:
                        er_res[h] = 0.0

                return {
                    "title": our_channel_fresh.title,
                    "username": clean_id if not clean_id.lstrip("-").isdigit() else None,
                    "link": f"https://t.me/{clean_id}" if not clean_id.lstrip("-").isdigit() else None,
                    "subscribers": subs,
                    "views": views_res,
                    "er": er_res,
                    "chat_id": chat_id
                }
        # ---------------------------------------

        # 2. Получить кэш из Redis
        logger.debug(f"🔍 [NovaStat] Проверка кэша Redis: {redis_data_key}")
        try:
            cached_data = await redis_client.get(redis_data_key)
            if cached_data:
                logger.info(f"✅ [Redis Cache Hit] Найдены данные в кэше для {redis_data_key}")
                return self.normalize_cache_keys(json.loads(cached_data))
            else:
                logger.info(f"❌ [Redis Cache Miss] Данных в кэше нет для {redis_data_key}")
        except Exception as e:
            logger.error(f"❌ [Redis Error] Ошибка чтения кэша: {e}")

        # 3. Если кэша нет - запускаем сбор
        logger.info(f"🚀 [NovaStat] Запуск сбора данных для {id_str} (redis_key: {redis_data_key})")
        await self.async_refresh_stats(id_str, days_limit, horizon, bot=bot)
        logger.debug(f"✅ [NovaStat] async_refresh_stats завершен для {id_str}")

        # 4. Проверяем результат (мог появиться в процессе сбора)
        # Если в процессе сбора ID уточнился - нам надо проверить новый ключ
        final_chat_id = None
        current_clean = self.normalize_identifier(id_str)
        if current_clean.lstrip("-").isdigit():
            final_chat_id = int(current_clean)
        else:
            # Re-resolve (lite lookup)
            our_ch = await db.channel.get_channel_by_title(current_clean)
            if our_ch:
                final_chat_id = our_ch.chat_id
            if not final_chat_id:
                ext_ch = await db.external_channel.get_by_username(current_clean)
                if not ext_ch and ("t.me/+" in current_clean or "joinchat/" in current_clean):
                    ext_ch = await db.external_channel.get_by_link(current_clean)
                if ext_ch:
                    final_chat_id = ext_ch.chat_id
        
        final_suffix = str(final_chat_id) if final_chat_id else current_clean
        final_redis_key = f"novastat:data:{final_suffix}:{horizon}"
        logger.debug(f"🔍 [NovaStat] Проверка финального кэша: {final_redis_key}")

        try:
            cached_data = await redis_client.get(final_redis_key)
            if cached_data:
                logger.info(f"✅ [Redis Final Hit] Найдены финальные данные в кэше для {final_redis_key}")
                res = json.loads(cached_data)
                if "error" in res:
                     logger.warning(f"⚠️ [NovaStat] В кэше сохранена ошибка: {res.get('error')}")
                     pass
                return self.normalize_cache_keys(res)
            else:
                logger.warning(f"❌ [Redis Final Miss] Финальных данных в кэше нет для {final_redis_key}")
        except Exception as e:
            logger.error(f"❌ [Redis Error] Ошибка чтения финального кэша: {e}")

        return None

    def _map_error(self, e: Exception) -> str:
        """Сопоставление технических ошибок с понятными пользователю сообщениями."""
        err_str = str(e)
        if "InviteHashInvalid" in err_str:
            return "Некорректная ссылка приглашения. Проверьте адрес."
        if "InviteHashExpired" in err_str:
            return "Ссылка приглашения устарела или отозвана."
        if "ChannelsTooMuch" in err_str:
            return "Техническое ограничение: бот перегружен каналами."
        if "USER_NOT_PARTICIPANT" in err_str:
            return "Бот не смог вступить в канал (нет автоприёма?)"
        if "CHAT_ADMIN_REQUIRED" in err_str:
            return "Требуются права администратора для просмотра."
        if "CHANNEL_PRIVATE" in err_str:
            return "Канал приватный и недоступен."
        if "без автоприема" in err_str:
            return err_str
        if ("No user has" in err_str and "as username" in err_str) or "Cannot find any entity" in err_str:
            return "Канал не найден или недоступен боту. Если канал приватный — убедитесь, что бот в нём есть."
        return f"{err_str}"

    async def async_refresh_stats(
        self, channel_identifier: str, days_limit: int, horizon: int, bot: Bot = None
    ):
        """Асинхронное обновление статистики в кэше и ExternalChannel"""
        clean_id = self.normalize_identifier(channel_identifier)
        lock_id = clean_id
        logger.info(f"🔄 [async_refresh_stats] START: channel={channel_identifier}, clean_id={clean_id}, horizon={horizon}h")
        
        # 1. Сначала пытаемся найти chat_id в базе, чтобы блокировка была единой 
        # (и для юзернейма, и для ID)
        our_channel = None
        chat_id = None
        
        if clean_id.lstrip("-").isdigit():
            chat_id = int(clean_id)
            our_channel = await db.channel.get_channel_by_chat_id(chat_id)
        else:
            # Поиск в своих по названию
            our_channel = await db.channel.get_channel_by_title(clean_id)
            if our_channel:
                chat_id = our_channel.chat_id
            
            # Поиск во внешних (только если не нашли в своих)
            if not chat_id:
                ext_ch = await db.external_channel.get_by_username(clean_id)
                if not ext_ch and ("t.me/+" in clean_id or "joinchat/" in clean_id):
                    ext_ch = await db.external_channel.get_by_link(clean_id)
                
                if ext_ch:
                    chat_id = ext_ch.chat_id

        if chat_id:
            lock_id = str(chat_id)

        if chat_id:
            lock_id = str(chat_id)

        # Redis Keys
        redis_lock_key = f"novastat:lock:{lock_id}:{horizon}"
        # Data key will be determined at the end (might change if we resolve ID)

        # 2. Захват блокировки (Redis SETNX)
        # Пытаемся занять ключ на 600 сек (10 мин)
        is_locked = await redis_client.set(redis_lock_key, "LOCKED", nx=True, ex=600)
        if not is_locked:
            logger.warning("⏳ [async_refresh_stats] Lock занят, выход")
            return
        logger.info(f"✅ [async_refresh_stats] Lock захвачен: {redis_lock_key}")

        try:
            logger.info("🛠 [async_refresh_stats] Начало сбора данных")
            # 3. Если канал "свой" - Fast Path (Redundant here but consistent)
            if our_channel:
                # Logic already handled in collect_stats fast path, 
                # BUT async_refresh_stats is also called by Scheduler!
                # So we MUST keep this logic here for scheduler.
                # Код тот же, что и был.
                
                if our_channel.novastat_24h > 0:
                    # ... (existing DB fetch logic) ...
                    # ... (skipped for brevity, assuming we keep logic but use Redis set) ...
                    # We need to retain the logic body but change set_cache call.
                    # Since I'm replacing the whole block, I need to rewrite it.
                    
                    logger.info(f"Канал {clean_id} (внутренний), берем из БД.")
                    subs = our_channel.subscribers_count
                    views_res = {
                        24: our_channel.novastat_24h,
                        48: our_channel.novastat_48h,
                        72: our_channel.novastat_72h,
                    }
                    er_res = {}
                    for h in [24, 48, 72]:
                        if subs > 0:
                            er_res[h] = round((views_res[h] / subs) * 100, 2)
                        else:
                            er_res[h] = 0.0

                    stats = {
                        "title": our_channel.title,
                        "username": clean_id if not clean_id.lstrip("-").isdigit() else None,
                        "link": f"https://t.me/{clean_id}" if not clean_id.lstrip("-").isdigit() else None,
                        "subscribers": subs,
                        "views": views_res,
                        "er": er_res,
                        "chat_id": chat_id
                    }
                    
                    # Сохраняем в Redis
                    await redis_client.set(f"novastat:data:{lock_id}:{horizon}", json.dumps(stats), ex=CACHE_TTL_SECONDS)
                    return
                
                # Если 0, продолжаем... (though Fast Path excludes this, but Scheduler might start fresh)

            # 4. Получаем данные через MTProto
            stats = None
            final_chat_id = chat_id
            
            # ... (Internal client logic) ...
            if our_channel and our_channel.session_path:
                # ... copy paste existing logic ...
                manager = SessionManager(our_channel.session_path)
                await manager.init_client()
                if manager.client:
                    try:
                        logger.info(f"Использование внутреннего клиента для {channel_identifier}")
                        stats = await self._collect_stats_impl(manager.client, chat_id or channel_identifier, days_limit)
                        if stats and stats.get("chat_id"):
                            final_chat_id = stats["chat_id"]
                    finally:
                        await manager.close()

            if not stats:
                # ... (External client logic) ...
                logger.info(f"Использование внешнего пула для {channel_identifier}")
                
                pinned_client_id = None
                try:
                    target_ext_ch = None
                    if final_chat_id: 
                        target_ext_ch = await db.external_channel.get_external_channel(final_chat_id)
                    elif not str(channel_identifier).strip().lstrip("-").isdigit(): 
                         target_ext_ch = await db.external_channel.get_by_username(channel_identifier)
                         if not target_ext_ch and ("t.me/+" in str(channel_identifier) or "joinchat" in str(channel_identifier)):
                             target_ext_ch = await db.external_channel.get_by_link(str(channel_identifier))
                    
                    if target_ext_ch:
                        pinned_client_id = target_ext_ch.pinned_client_id
                except Exception:
                    pass

                for _ in range(3): 
                    client_data = await self.get_external_client(preferred_client_id=pinned_client_id)
                    if not client_data:
                        break
                    
                    client_obj, manager = client_data
                    logger.info(f"Выбран внешний клиент: {client_obj.alias} (ID: {client_obj.id})")
                    
                    try:
                        stats = await self._collect_stats_impl(manager.client, channel_identifier, days_limit)
                        if stats:
                            if stats.get("chat_id"):
                                final_chat_id = stats["chat_id"]
                            
                            successful_client_id = client_obj.id
                            break 
                    except Exception as e:
                        logger.warning(f"Клиент {client_obj.alias} не справился с {channel_identifier}: {e}")
                    finally:
                        await manager.close()

            if stats:
                logger.info("✅ [async_refresh_stats] Статистика успешно собрана")
                # 5. Сохранение данных в БД (Persistent)
                if final_chat_id:
                    v = stats["views"]
                    if our_channel:
                        logger.info(f"📥 Обновление статистики внутреннего канала {final_chat_id} в БД")
                        await db.channel.update_channel_by_chat_id(
                            final_chat_id,
                            novastat_24h=v.get(24, 0),
                            novastat_48h=v.get(48, 0),
                            novastat_72h=v.get(72, 0),
                            subscribers_count=stats["subscribers"]
                        )
                    else:
                        logger.info(f"📥 Сохранение данных внешнего канала {final_chat_id} в БД")
                        invite_link = None
                        if "t.me/+" in clean_id or "joinchat/" in clean_id:
                            invite_link = clean_id
                        
                        current_pinned_client = locals().get('successful_client_id', None)

                        await db.external_channel.upsert_external_channel(
                            chat_id=final_chat_id,
                            title=stats["title"],
                            username=stats.get("username"),
                            invite_link=invite_link,
                            subscribers_count=stats["subscribers"],
                            novastat_24h=v.get(24, 0),
                            novastat_48h=v.get(48, 0),
                            novastat_72h=v.get(72, 0),
                            pinned_client_id=current_pinned_client 
                        )
                    
                # 6. Обновление кэша в Redis
                cache_final_key = f"novastat:data:{final_chat_id}:{horizon}" if final_chat_id else f"novastat:data:{lock_id}:{horizon}"
                logger.info(f"💾 [async_refresh_stats] Сохранение в Redis: {cache_final_key}")
                
                await redis_client.set(cache_final_key, json.dumps(stats), ex=CACHE_TTL_SECONDS)
                
                # Если ключ изменился (был юзернейм, стал ID), сохраним и под старым ключом (алиас), или просто заьбем.
                # Лучше сохранить и под старым, если они разные.
                final_redis_key = f"novastat:data:{lock_id}:{horizon}"
                if cache_final_key != final_redis_key:
                    # Также сохраним под юзернеймом/ссылкой
                     await redis_client.set(final_redis_key, json.dumps(stats), ex=CACHE_TTL_SECONDS)

            else:
                logger.error("❌ [async_refresh_stats] Сбор статистики НЕ УДАЛСЯ (stats=None)")
                # Сохраняем ошибку в кэш, чтобы не долбить (TTL короче, например 5 минут)
                err_json = json.dumps({"error": "Не удалось собрать статистику"})
                await redis_client.set(f"novastat:data:{lock_id}:{horizon}", err_json, ex=300)

        except Exception as e:
            error_msg = self._map_error(e)
            logger.error(f"❌ [async_refresh_stats] EXCEPTION: {e}", exc_info=True)
            err_json = json.dumps({"error": error_msg})
            # Сохраняем ошибку
            await redis_client.set(f"novastat:data:{lock_id}:{horizon}", err_json, ex=300)
        finally:
            # Разблокируем
            logger.debug(f"🔓 [async_refresh_stats] Снятие блокировки: {redis_lock_key}")
            await redis_client.delete(redis_lock_key)
            logger.info("✅ [async_refresh_stats] END")

    async def _collect_stats_impl(
        self, client: TelegramClient, channel_identifier: str, days_limit: int
    ) -> Optional[Dict]:
        """Внутренняя реализация сбора статистики"""
        tz = ZoneInfo(TIMEZONE)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)

        # 0. Если нам уже передали готовую сущность (из планировщика) - используем её
        if not isinstance(channel_identifier, (str, int)):
            entity = channel_identifier
            logger.info(f"✅ Использование переданной сущности напрямую: тип={type(entity).__name__}")
        else:
            # Нормализация для Telethon
            clean_target = self.normalize_identifier(str(channel_identifier))
            
            # Если это числовой ID, приводим к int для получения сущности
            target_entity = clean_target
            if clean_target.lstrip("-").isdigit():
                target_entity = int(clean_target)
                logger.info(f"🔢 Приведение строкового ID '{clean_target}' к целому числу для Telethon")

            logger.info(f"📍 Начало сбора статистики для '{clean_target}' (из оригинала: '{channel_identifier}')")
            
            entity = None
            join_attempted = False
            error_str = "Неизвестная ошибка"

            for attempt in range(3):
                try:
                    # 0.1 Если это инвайт-ссылка, пробуем проверить её
                    if isinstance(target_entity, str) and ("t.me/+" in target_entity or "joinchat/" in target_entity):
                        try:
                            hash_arg = target_entity.split("/")[-1].replace("+", "")
                            logger.info(f"🛠 [Приватная ссылка] Пробую CheckChatInviteRequest('{hash_arg}')")
                            res = await client(functions.messages.CheckChatInviteRequest(hash=hash_arg))
                            
                            # Если мы уже в чате, там будет объект chat
                            if hasattr(res, 'chat') and res.chat:
                                entity = res.chat
                                logger.info(f"✅ Сущность получена через CheckChatInvite (уже в канале): ID={entity.id}")
                                break
                            
                            # Если мы не в чате, получим ChatInvite (не entity)
                            # В этом случае провалимся дальше в логику вступления
                            logger.info("ℹ️ Ссылка валидна, но мы не в канале. Переход к Join.")
                            error_str = "USER_NOT_PARTICIPANT" # Симулируем ошибку для триггера Join
                        except Exception as check_err:
                            error_str = str(check_err)
                            logger.warning(f"❌ CheckChatInviteRequest не удался: {error_str}")

                    # 0.2 Обычный get_entity (если еще не получили)
                    if not entity:
                        logger.info(f"🔍 [Попытка {attempt + 1}/3] получение сущности ({target_entity})")
                        entity = await client.get_entity(target_entity)
                        logger.info(f"✅ Сущность успешно получена: ID={entity.id}, тип={type(entity).__name__}")
                        break  # Успех
                except Exception as e:
                    error_str = str(e)
                    logger.warning(f"⚠️ получение сущности не удалось: {error_str}")

                    # Если канал не найден — пробуем запрос разрешения юзернейма
                    if ("No user has" in error_str or "Could not find" in error_str) and not str(clean_target).lstrip("-").isdigit():
                        try:
                            logger.info(f"🛠 [Разрешитель] Пробую ResolveUsernameRequest('{clean_target}')")
                            res = await client(functions.contacts.ResolveUsernameRequest(clean_target))
                            if res.chats:
                                entity = res.chats[0]
                                logger.info(f"✅ Разрешитель успешно нашел канал: ID={entity.id}")
                                break
                        except Exception as res_err:
                            logger.warning(f"❌ Запрос ResolveUsernameRequest не удался: {res_err}")

                # Если это ошибка доступа и мы еще не пытались join
                if (
                    "USER_NOT_PARTICIPANT" in error_str
                    or "CHANNEL_PRIVATE" in error_str
                    or "CHAT_ADMIN_REQUIRED" in error_str
                ) and not join_attempted:
                    logger.info(
                        f"Канал {channel_identifier} требует вступления, попытка join..."
                    )

                    last_join_error = ""
                    # Попытаться присоединиться (до 3 попыток по запросу пользователя)
                    for join_attempt in range(3):
                        try:
                            if isinstance(channel_identifier, str):
                                if "t.me/" in channel_identifier:
                                    if "t.me/+" in channel_identifier or "joinchat" in channel_identifier:
                                        hash_arg = channel_identifier.split("/")[-1].replace("+", "")
                                        await client(functions.messages.ImportChatInviteRequest(hash=hash_arg))
                                    else:
                                        username = channel_identifier.split("/")[-1]
                                        await client(functions.channels.JoinChannelRequest(channel=username))
                                elif channel_identifier.startswith("@"):
                                    await client(functions.channels.JoinChannelRequest(channel=channel_identifier[1:]))
                                else:
                                    await client(functions.channels.JoinChannelRequest(channel=channel_identifier))
                            
                            logger.info(f"✅ Вступление успешно ({join_attempt+1}/3) для {channel_identifier}")
                            join_attempted = True
                            await asyncio.sleep(2) # Пауза для обновления кэша Telegram
                            break 
                        except Exception as join_error:
                            last_join_error = str(join_error)
                            logger.warning(f"⚠️ Попытка вступления {join_attempt+1}/3 не удалась: {last_join_error}")
                            
                            if "FLOOD" in last_join_error:
                                break 
                            
                            if join_attempt == 0:
                                await asyncio.sleep(1) # Ждем 1 сек после первой попытки
                            elif join_attempt == 1:
                                await asyncio.sleep(2) # Ждем 2 сек после второй попытки
                            else:
                                # После 3 неудачных попыток
                                error_msg = f"Не удалось вступить в канал {channel_identifier}. Возможно, ссылка без автоприема (требуется одобрение админа), и клиент-помощник не может попасть на канал."
                                logger.error(error_msg)
                                raise Exception(error_msg)
                    
                    join_attempted = True 
                    continue 

                # Если не последняя попытка - ждем и пробуем снова
                if attempt < 2:  # Not the last attempt
                    delay = attempt + 1  # 1s on first retry, 2s on second retry
                    logger.warning(
                        f"Попытка get_entity {attempt + 1} не удалась для {channel_identifier}: {error_str}. Повтор через {delay}с..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # Последняя попытка не удалась
                    error_msg = f"Не удалось получить информацию о канале {channel_identifier} после всех попыток: {error_str}"
                    logger.error(error_msg)
                    raise Exception(self._map_error(error_str))

        if not entity:
            error_msg = f"Сущность не найдена для {channel_identifier} после всех попыток"
            logger.error(error_msg)
            raise Exception("Не удалось найти канал.")

        # --- INTERNAL CHANNEL CHECK ---
        # Проверяем, не является ли найденный канал нашим "внутренним"
        # Это актуально, если пользователь дал инвайт-ссылку на свой же канал.
        # Мы только что узнали ID (entity.id) и можем проверить его в БД.
        try:
            resolved_chat_id = utils.get_peer_id(entity)
            fresh_internal = await db.channel.get_channel_by_chat_id(resolved_chat_id)
            
            if fresh_internal:
                logger.info(f"⚡ Fast Path (Resolved): Канал {resolved_chat_id} оказался внутренним. Прерываем MTProto сбор и отдаем данные из БД.")
                
                subs = fresh_internal.subscribers_count
                views_res = {
                    24: fresh_internal.novastat_24h,
                    48: fresh_internal.novastat_48h,
                    72: fresh_internal.novastat_72h,
                }
                er_res = {}
                for h in [24, 48, 72]:
                    if subs > 0:
                        er_res[h] = round((views_res[h] / subs) * 100, 2)
                    else:
                        er_res[h] = 0.0

                return {
                    "title": fresh_internal.title,
                    "username": getattr(entity, 'username', None),
                    "link": f"https://t.me/{getattr(entity, 'username', '')}" if getattr(entity, 'username', None) else None,
                    "subscribers": subs,
                    "views": views_res,
                    "er": er_res,
                    "chat_id": resolved_chat_id
                }
        except Exception as check_internal_err:
            logger.warning(f"Ошибка при проверке внутреннего канала после резолва: {check_internal_err}")
        # ------------------------------

        title = getattr(entity, "title", getattr(entity, "username", str(entity)))
        username = getattr(entity, "username", None)
        logger.info(
            f"Получена информация о сущности: title={title}, username={username}"
        )

        # Получить подписчиков
        try:
            logger.debug(
                f"Получение полной информации о канале для {channel_identifier}"
            )
            full = await client(
                functions.channels.GetFullChannelRequest(channel=entity)
            )
            members = int(getattr(full.full_chat, "participants_count", 0) or 0)
            logger.debug(f"Получено {members} подписчиков для {channel_identifier}")
        except RPCError as e:
            logger.warning(
                f"Не удалось получить подписчиков для {channel_identifier}: {e}"
            )
            members = 0
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка получения подписчиков для {channel_identifier}: {e}"
            )
            members = 0

        # Получить посты
        cutoff_utc = now_utc - timedelta(days=days_limit)
        raw_points: List[Tuple[float, int]] = []
        logger.debug(
            f"Начало итерации сообщений для {channel_identifier}, cutoff={cutoff_utc}"
        )

        try:
            async for m in client.iter_messages(
                entity, offset_date=cutoff_utc, reverse=True
            ):
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
        except Exception as iter_error:
            logger.error(
                f"Ошибка итерации сообщений для {channel_identifier}: {iter_error}"
            )
            # Продолжаем с тем что успели собрать

        logger.debug(f"Собрано {len(raw_points)} точек данных для {channel_identifier}")

        # Определить ссылку
        link = None
        if username:
            link = f"https://t.me/{username}"
        elif isinstance(channel_identifier, str) and "t.me" in channel_identifier:
            link = channel_identifier

        if not raw_points:
            # Нет постов или просмотров, вернуть 0
            return {
                "title": title,
                "username": username,
                "link": link,
                "subscribers": members,
                "views": {24: 0, 48: 0, 72: 0},
                "er": {24: 0.0, 48: 0.0, 72: 0.0},
            }

        # Фильтрация аномалий
        views_list = [v for (_, v) in raw_points]
        med = int(median(views_list))
        threshold = med * ANOMALY_FACTOR if med > 0 else None

        if threshold:
            valid_points = [(age, v) for (age, v) in raw_points if v <= threshold]
        else:
            valid_points = raw_points

        if not valid_points:
            return {
                "title": title,
                "username": username,
                "link": link,
                "subscribers": members,
                "views": {24: 0, 48: 0, 72: 0},
                "er": {24: 0.0, 48: 0.0, 72: 0.0},
            }

        # Интерполяция
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
            "title": title,
            "username": username,
            "link": link,
            "subscribers": members,
            "views": views_res,
            "er": er_res,
            "chat_id": utils.get_peer_id(entity)
        }


novastat_service = NovaStatService()
