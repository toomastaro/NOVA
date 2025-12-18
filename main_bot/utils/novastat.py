import asyncio
import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from statistics import median
from typing import List, Tuple, Dict, Optional
from pathlib import Path

from aiogram import Bot
from telethon import TelegramClient
from telethon.tl import functions, types
from telethon.errors import RPCError
from config import Config

from main_bot.database.db import db
from main_bot.utils.session_manager import SessionManager

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

    async def get_external_client(self) -> Optional[tuple]:
        """Получить наименее используемого внешнего MtClient и SessionManager (алгоритм least-used)"""
        client = await db.mt_client.get_next_external_client()

        if not client:
            logger.warning("Нет активных внешних клиентов")
            return None

        logger.debug(
            f"🔄 Выбран внешний клиент {client.id} ({client.alias}) с использованием={client.usage_count}"
        )

        session_path = Path(client.session_path)

        if not session_path.exists():
            logger.error(
                f"Файл сессии не найден для внешнего клиента {client.id}: {session_path}"
            )
            return None

        manager = SessionManager(session_path)
        await manager.init_client()

        if not manager.client:
            logger.error(
                f"Не удалось инициализировать клиент для внешнего клиента {client.id}"
            )
            return None

        # Увеличить счетчик использования
        await db.mt_client.increment_usage(client.id)
        logger.debug(f"Увеличен счетчик использования для клиента {client.id}")

        return (client, manager)

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
        Собрать статистику для канала с кэшированием.
        """
        channel_identifier = str(channel_identifier)

        # 1. Получить кэш один раз
        cache = await db.novastat_cache.get_cache(channel_identifier, horizon)

        # 2. Проверить "свежесть" в памяти
        if cache and not cache.refresh_in_progress and not cache.error_message:
            current_time = int(time.time())
            if (current_time - cache.updated_at) < CACHE_TTL_SECONDS:
                data = self.normalize_cache_keys(cache.value_json)
                views = data.get("views", {})
                if views.get(24, 0) > 0:
                    return data
                logger.debug(
                    f"В кэше 0 просмотров для {channel_identifier}, принудительное обновление."
                )

        # 3. Если идет обновление - вернуть старые данные
        if cache and cache.refresh_in_progress:
            if cache.value_json:
                return self.normalize_cache_keys(cache.value_json)
            return None

        # 4. Обновить синхронно (ждать результата)
        logger.debug(
            f"Промах кэша для {channel_identifier}, получение свежих данных..."
        )
        await self.async_refresh_stats(channel_identifier, days_limit, horizon, bot=bot)

        # 5. Получить результат
        cache = await db.novastat_cache.get_cache(channel_identifier, horizon)
        if cache and cache.value_json and not cache.error_message:
            return self.normalize_cache_keys(cache.value_json)

        return None

    def _map_error(self, e: Exception) -> str:
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
        return f"{err_str}"

    async def async_refresh_stats(
        self, channel_identifier: str, days_limit: int, horizon: int, bot: Bot = None
    ):
        """Асинхронное обновление статистики в кэше"""
        try:
            # Попытка захватить атомарную блокировку
            lock_acquired = await db.novastat_cache.try_acquire_refresh_lock(
                channel_identifier, horizon
            )
            if not lock_acquired:
                logger.debug(
                    f"Обновление для {channel_identifier} уже выполняется другим процессом."
                )
                return

            # Шаг 1: Проверить, является ли канал "своим" (в нашем боте)
            our_channel = None
            channel_id = None

            # Попытаться найти канал по username или ссылке
            try:
                if isinstance(channel_identifier, int) or (
                    isinstance(channel_identifier, str)
                    and channel_identifier.lstrip("-").replace(" ", "").isdigit()
                ):
                    channel_id = int(channel_identifier)
                    our_channel = await db.channel.get_channel_by_chat_id(channel_id)
                    username = our_channel.title if our_channel else str(channel_id)
                else:
                    if "t.me/" in channel_identifier:
                        username = channel_identifier.split("/")[-1].replace("@", "")
                    elif channel_identifier.startswith("@"):
                        username = channel_identifier[1:]
                    else:
                        username = channel_identifier.replace("@", "")

                    # Поиск канала в базе
                    channels = await db.channel.get_channels()
                    for ch in channels:
                        if ch.title == username or (
                            hasattr(ch, "username") and ch.username == username
                        ):
                            our_channel = ch
                            channel_id = ch.chat_id
                            break
            except Exception as e:
                logger.debug(
                    f"Не удалось определить, является ли канал {channel_identifier} нашим: {e}"
                )

            # Шаг 2: Если канал "свой", использовать данные из БД (обновляемые ежечасно)
            if our_channel and channel_id:
                subs = our_channel.subscribers_count

                # Если подписчиков нет, пробуем получить их прямо сейчас
                if subs <= 0:
                    try:
                        logger.info(
                            f"Количество подписчиков 0 для {channel_id}, попытка получения..."
                        )

                        updated_via_bot = False

                        # 1. Попытка через Bot API (если передан бот)
                        if bot:
                            try:
                                count = await bot.get_chat_member_count(channel_id)
                                if count > 0:
                                    await db.channel.update_channel_by_chat_id(
                                        our_channel.chat_id, subscribers_count=count
                                    )
                                    our_channel.subscribers_count = count
                                    subs = count
                                    updated_via_bot = True
                                    logger.info(
                                        f"Обновлено количество подписчиков для {our_channel.chat_id} через Bot API: {subs}"
                                    )
                            except Exception as e_bot:
                                logger.info(
                                    f"Ошибка получения подписчиков через Bot API для {channel_id}: {e_bot}"
                                )

                        # 2. Если Bot API не сработал - пробуем External Client
                        if not updated_via_bot:
                            # Используем external клиент
                            client_data = await self.get_external_client()
                            if client_data:
                                client, manager = client_data
                                try:
                                    # Получаем entity
                                    # Для int ID может потребоваться PeerChannel или просто int
                                    entity = await manager.client.get_entity(channel_id)

                                    # get_entity часто возвращает Chat/Channel с participants_count
                                    if (
                                        hasattr(entity, "participants_count")
                                        and entity.participants_count
                                    ):
                                        subs = entity.participants_count
                                    else:
                                        # Возврат к get_full_channel, если простой entity не имеет счетчика
                                        full = await manager.client(
                                            functions.channels.GetFullChannelRequest(
                                                entity
                                            )
                                        )
                                        subs = full.full_chat.participants_count

                                    if subs > 0:
                                        await db.channel.update_channel_by_chat_id(
                                            our_channel.chat_id, subscribers_count=subs
                                        )
                                        # Обновляем объект в памяти для этого запуска
                                        our_channel.subscribers_count = subs
                                        logger.info(
                                            f"Обновлено начальное количество подписчиков для {our_channel.chat_id}: {subs}"
                                        )

                                finally:
                                    # Обязательно закрываем сессию
                                    await manager.close()
                    except Exception as e:
                        logger.warning(
                            f"Не удалось получить начальное количество подписчиков для {channel_id}: {e}"
                        )

                # Если статистики нет (0 просмотров) и есть сессия - обновить через свой клиент
                if our_channel.novastat_24h == 0 and our_channel.session_path:
                    try:
                        logger.info(
                            f"Просмотры 0 для 'нашего' канала {channel_id}, пробуем внутренний клиент..."
                        )
                        # SessionManager импортируется из utils
                        manager = SessionManager(our_channel.session_path)
                        await manager.init_client()
                        if manager.client:
                            try:
                                entity = await manager.client.get_entity(channel_id)
                                # _collect_stats_impl доступен в этом классе
                                stats = await self._collect_stats_impl(
                                    manager.client, entity, days_limit=4
                                )
                                if stats and "views" in stats:
                                    v = stats["views"]
                                    await db.channel.update_channel_by_id(
                                        our_channel.id,
                                        novastat_24h=v.get(24, 0),
                                        novastat_48h=v.get(48, 0),
                                        novastat_72h=v.get(72, 0),
                                    )
                                    # Обновление объекта в памяти
                                    our_channel.novastat_24h = v.get(24, 0)
                                    our_channel.novastat_48h = v.get(48, 0)
                                    our_channel.novastat_72h = v.get(72, 0)
                                    logger.info(
                                        f"Обновлены просмотры через внутренний клиент: {v}"
                                    )
                            finally:
                                await manager.close()
                    except Exception as e:
                        logger.warning(
                            f"Не удалось получить просмотры через внутренний клиент: {e}"
                        )

                logger.info(
                    f"Канал {channel_identifier} это наш канал (id={channel_id}), используем стат. из БД"
                )

                # Формируем статистику из БД
                views_res = {
                    24: our_channel.novastat_24h,
                    48: our_channel.novastat_48h,
                    72: our_channel.novastat_72h,
                }

                er_res = {}
                subs = our_channel.subscribers_count
                for h in [24, 48, 72]:
                    if subs > 0:
                        er_res[h] = round((views_res[h] / subs) * 100, 2)
                    else:
                        er_res[h] = 0.0

                stats = {
                    "title": our_channel.title,
                    "username": getattr(our_channel, "username", username),
                    "link": (
                        f"https://t.me/{getattr(our_channel, 'username', username)}"
                        if getattr(our_channel, "username", None)
                        else None
                    ),
                    "subscribers": subs,
                    "views": views_res,
                    "er": er_res,
                }

                await db.novastat_cache.set_cache(
                    channel_identifier, horizon, stats, error_message=None
                )
                return

            # Шаг 3: Канал не "свой" или нет internal клиента - использовать external клиента
            logger.debug(f"Используем внешний клиент для канала {channel_identifier}")

            # Получить external клиента
            client_data = await self.get_external_client()
            if not client_data:
                await db.novastat_cache.set_cache(
                    channel_identifier,
                    horizon,
                    {},
                    error_message="Нет доступных клиентов для анализа",
                )
                return

            client_obj, manager = client_data

            try:
                # Собрать статистику
                stats = await self._collect_stats_impl(
                    manager.client, channel_identifier, days_limit
                )

                if stats:
                    # Сохранить в кэш
                    await db.novastat_cache.set_cache(
                        channel_identifier, horizon, stats, error_message=None
                    )
                else:
                    await db.novastat_cache.set_cache(
                        channel_identifier,
                        horizon,
                        {},
                        error_message="Не удалось собрать статистику",
                    )
            finally:
                await manager.close()

        except Exception as e:
            error_msg = self._map_error(e)

            await db.novastat_cache.set_cache(
                channel_identifier, horizon, {}, error_message=error_msg
            )
        finally:
            # Сбросить флаг обновления
            await db.novastat_cache.mark_refresh_in_progress(
                channel_identifier, horizon, False
            )

    async def _collect_stats_impl(
        self, client: TelegramClient, channel_identifier: str, days_limit: int
    ) -> Optional[Dict]:
        """Внутренняя реализация сбора статистики"""
        tz = ZoneInfo(TIMEZONE)
        now_local = datetime.now(tz)
        now_utc = now_local.astimezone(timezone.utc)

        # Попытка получить entity с 3 попытками (для авто-приема)
        # Если канал приватный с автоприемом, может потребоваться несколько попыток
        entity = None
        entity = None
        # last_error = None
        join_attempted = False

        for attempt in range(3):
            try:
                entity = await client.get_entity(channel_identifier)
                logger.info(
                    f"Успешно получен entity для {channel_identifier} с попытки {attempt + 1}"
                )
                break  # Success
            except Exception as e:
                # last_error = e
                error_str = str(e)

                # Если это ошибка доступа и мы еще не пытались join
                if (
                    "USER_NOT_PARTICIPANT" in error_str
                    or "CHANNEL_PRIVATE" in error_str
                ) and not join_attempted:
                    logger.info(
                        f"Канал {channel_identifier} требует вступления, попытка join..."
                    )

                    # Попытаться присоединиться через SessionManager
                    try:

                        # Попытка join
                        if isinstance(channel_identifier, str):
                            if "t.me/" in channel_identifier:
                                # Это ссылка
                                if (
                                    "t.me/+" in channel_identifier
                                    or "joinchat" in channel_identifier
                                ):
                                    # Приватная ссылка приглашения
                                    hash_arg = channel_identifier.split("/")[
                                        -1
                                    ].replace("+", "")
                                    await client(
                                        functions.messages.ImportChatInviteRequest(
                                            hash=hash_arg
                                        )
                                    )
                                else:
                                    # Публичная ссылка
                                    username = channel_identifier.split("/")[-1]
                                    await client(
                                        functions.channels.JoinChannelRequest(
                                            channel=username
                                        )
                                    )
                            elif channel_identifier.startswith("@"):
                                # Юзернейм
                                await client(
                                    functions.channels.JoinChannelRequest(
                                        channel=channel_identifier[1:]
                                    )
                                )
                            else:
                                # Предполагаем юзернейм без @
                                await client(
                                    functions.channels.JoinChannelRequest(
                                        channel=channel_identifier
                                    )
                                )
                        else:
                            logger.warning(
                                f"Невозможно автоматически вступить в канал по ID/Entity: {channel_identifier}"
                            )

                        join_attempted = True
                        logger.info(
                            f"Попытка вступления успешна для {channel_identifier}, повтор get_entity..."
                        )

                        # Подождать немного и попробовать снова
                        await asyncio.sleep(1)
                        continue

                    except Exception as join_error:
                        logger.error(
                            f"Ошибка вступления для {channel_identifier}: {join_error}"
                        )
                        join_attempted = True

                # Если не последняя попытка - ждем и пробуем снова
                if attempt < 2:  # Not the last attempt
                    delay = attempt + 1  # 1s on first retry, 2s on second retry
                    logger.warning(
                        f"Попытка get_entity {attempt + 1} не удалась для {channel_identifier}: {e}. Повтор через {delay}с..."
                    )
                    await asyncio.sleep(delay)
                else:
                    # Последняя попытка не удалась
                    logger.error(
                        f"get_entity не удалось после 3 попыток для {channel_identifier}: {e}"
                    )

                    # Проверить, стал ли клиент подписчиком (если join был выполнен)
                    if join_attempted and "USER_NOT_PARTICIPANT" in error_str:
                        # Join был, но клиент все равно не участник
                        # Это значит либо ссылка без автоприема, либо проблемы с Telegram
                        raise Exception(
                            "Не удалось вступить в канал. Вероятно, ссылка не имеет автоприёма (требуется одобрение админа)."
                        )

                    # Отправить alert для других ошибок доступа
                    if (
                        "USER_NOT_PARTICIPANT" in error_str
                        or "CHAT_ADMIN_REQUIRED" in error_str
                        or "CHANNEL_PRIVATE" in error_str
                    ):
                        from main_bot.utils.support_log import (
                            send_support_alert,
                            SupportAlert,
                        )
                        from instance_bot import bot as main_bot_obj

                        # Попытка получить информацию о канале
                        channel = None
                        channel_id = None
                        try:
                            # Извлечь ID канала из идентификатора если это ссылка
                            if (
                                isinstance(channel_identifier, str)
                                and "t.me/" in channel_identifier
                            ):
                                username = channel_identifier.split("/")[-1]
                                channel = await db.get_channel_by_username(username)
                                if channel:
                                    channel_id = channel.chat_id
                        except Exception:
                            pass

                        safe_username = (
                            channel_identifier
                            if isinstance(channel_identifier, str)
                            else str(channel_identifier)
                        )

                        await send_support_alert(
                            main_bot_obj,
                            SupportAlert(
                                event_type="STATS_ACCESS_DENIED",
                                client_id=None,  # External client, we don't track which one
                                client_alias=None,
                                pool_type="external",
                                channel_id=channel_id,
                                channel_username=(
                                    safe_username if not channel_id else None
                                ),
                                is_our_channel=channel is not None,
                                error_code=(
                                    error_str.split("(")[0].strip()
                                    if "(" in error_str
                                    else error_str[:50]
                                ),
                                error_text=f"Не удалось получить статистику канала: {error_str[:100]}",
                            ),
                        )

                    return None

        if not entity:
            logger.error(f"Entity is None для {channel_identifier} после всех попыток")
            return None

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
        }


novastat_service = NovaStatService()
