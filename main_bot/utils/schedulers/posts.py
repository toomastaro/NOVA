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
import re
import html
import time
from pathlib import Path
from typing import Dict, List

from aiogram import types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.utils.tg_utils import set_channel_session
from main_bot.utils.lang.language import text
from main_bot.utils.cpm_utils import generate_cpm_report
from main_bot.utils.report_signature import get_report_signatures
from main_bot.utils.schemas import MessageOptions
from main_bot.utils.session_manager import SessionManager
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)

# Семафор для ограничения одновременных отправлений (соблюдение лимитов Telegram)
sem = asyncio.Semaphore(10)


async def get_views_for_batch(chat_id: int, message_ids: List[int]) -> Dict[int, int]:
    """Получить количество просмотров для списка сообщений в одном канале пачкой"""
    channel = await db.channel.get_channel_by_chat_id(chat_id)
    if not channel:
        return {}

    session_path = None
    if channel.session_path:
        session_path = Path(channel.session_path)
    else:
        res = await set_channel_session(chat_id)
        if isinstance(res, dict) and res.get("success"):
            session_path = Path(res.get("session_path"))
        elif isinstance(res, Path):
            session_path = res

    views_map = {mid: 0 for mid in message_ids}
    if session_path:
        async with SessionManager(session_path) as session:
            if session:
                views_obj = await session.get_views(chat_id, message_ids)
                if views_obj and views_obj.views:
                    for i, v_obj in enumerate(views_obj.views):
                        # views_obj.views соответствует порядку message_ids
                        mid = message_ids[i]
                        views_map[mid] = v_obj.views or 0
    return views_map, channel


PROCESSING_POSTS = set()


@safe_handler("Постинг: отправка поста (Background)")
async def send(post: Post):
    """
    Отправить пост в каналы (Унифицированный HTML + Invisible Link).
    Отказ от copyMessage и бэкап-канала.
    """
    try:
        # 1. Извлекаем и валидируем опции
        try:
            message_options = MessageOptions(**post.message_options)
        except Exception as e:
            logger.error(f"Ошибка валидации MessageOptions для поста {post.id}: {e}")
            message_options = MessageOptions()  # Фоллбек

        # 2. Адаптация данных (Миграция на лету для старых постов)
        html_text = (
            message_options.html_text
            or message_options.text
            or message_options.caption
            or ""
        )
        media_value = (
            message_options.media_value
            or message_options.photo
            or message_options.video
            or message_options.animation
        )
        media_type = message_options.media_type
        is_inv = message_options.is_invisible

        # Если file_id обернут в Media схему - достаем строку
        if hasattr(media_value, "file_id"):
            media_value = media_value.file_id

        # Авто-определение типа если не задан
        if not media_type:
            if message_options.photo:
                media_type = "photo"
            elif message_options.video:
                media_type = "video"
            elif message_options.animation:
                media_type = "animation"
            else:
                media_type = "text"

        logger.info(
            f"🚀 Старт рассылки поста {post.id}. Метод: {'Invisible' if is_inv else 'Native'}, Каналов: {len(post.chat_ids)}"
        )

        error_send = []
        success_send = []

        # 3. Цикл публикации
        for chat_id in post.chat_ids:
            async with sem:  # Ограничиваем количество одновременных запросов
                channel = await db.channel.get_channel_by_chat_id(chat_id)
                if not channel or not channel.subscribe:
                    continue

                try:
                    # Подготовка общих настроек
                    reply_markup = keyboards.post_kb(post=post)

                    # ВАРИАНТ 1: Invisible Link (Длинный пост или принудительно)
                    if is_inv or (len(html_text) > 1024 and media_type != "text"):
                        # Если это был старый длинный пост, пробуем спасти его через Invisible Link
                        # Но для полноценной работы медиа должно быть уже сохранено локально (URL).
                        # Если это file_id, Telegram покажет его как текстовую ссылку (не идеально, но лучше чем сбой).

                        preview_options = types.LinkPreviewOptions(
                            is_disabled=False,
                            prefer_large_media=True,
                            show_above_text=not message_options.show_caption_above_media,
                        )

                        post_message = await bot.send_message(
                            chat_id=chat_id,
                            text=html_text,
                            parse_mode="HTML",
                            reply_markup=reply_markup,
                            link_preview_options=preview_options,
                            disable_notification=message_options.disable_notification,
                        )

                    # ВАРИАНТ 2: Native Media (Короткий пост или чисто текст)
                    else:
                        if media_type == "photo":
                            post_message = await bot.send_photo(
                                chat_id=chat_id,
                                photo=media_value,
                                caption=html_text,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                show_caption_above_media=message_options.show_caption_above_media,
                                disable_notification=message_options.disable_notification,
                            )
                        elif media_type == "video":
                            post_message = await bot.send_video(
                                chat_id=chat_id,
                                video=media_value,
                                caption=html_text,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                show_caption_above_media=message_options.show_caption_above_media,
                                disable_notification=message_options.disable_notification,
                            )
                        elif media_type == "animation":
                            post_message = await bot.send_animation(
                                chat_id=chat_id,
                                animation=media_value,
                                caption=html_text,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                show_caption_above_media=message_options.show_caption_above_media,
                                disable_notification=message_options.disable_notification,
                            )
                        else:  # Pure text
                            post_message = await bot.send_message(
                                chat_id=chat_id,
                                text=html_text,
                                parse_mode="HTML",
                                reply_markup=reply_markup,
                                disable_notification=message_options.disable_notification,
                                link_preview_options=types.LinkPreviewOptions(
                                    is_disabled=True
                                ),
                            )

                    logger.debug(
                        f"Пост {post.id} успешно отправлен в {chat_id} (msg: {post_message.message_id})"
                    )

                    # Пин сообщения
                    if post.pin_time:
                        try:
                            await bot.pin_chat_message(
                                chat_id=chat_id,
                                message_id=post_message.message_id,
                                disable_notification=message_options.disable_notification,
                            )
                        except Exception as pin_err:
                            logger.warning(
                                f"Не удалось закрепить пост {post.id} в {chat_id}: {pin_err}"
                            )

                    # Сбор данных для БД
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
                            "delete_time": (
                                post.delete_time + current_time
                                if post.delete_time
                                else None
                            ),
                            "created_timestamp": current_time,
                            "report": post.report,
                            "cpm_price": post.cpm_price,
                            "message_options": post.message_options,
                        }
                    )

                except Exception as e:
                    logger.error(f"Ошибка отправки поста {post.id} в {chat_id}: {e}")
                    error_send.append({"chat_id": chat_id, "error": str(e)})

                # Небольшая пауза между каналами для соблюдения лимитов
                await asyncio.sleep(0.05)

        # 4. Финализация (БД и Отчеты)
        if success_send:
            await db.published_post.add_many_published_post(posts=success_send)
            logger.info(
                f"✅ Успешно опубликовано: {len(success_send)} каналов для поста {post.id}"
            )

        await db.post.clear_posts(post_ids=[post.id])

        # Уведомление админа
        if post.report or error_send:
            await _send_admin_report(post, success_send, error_send)

    except Exception as e:
        logger.error(
            f"Глобальная ошибка в планировщике для поста {post.id}: {e}", exc_info=True
        )
    finally:
        PROCESSING_POSTS.discard(post.id)


async def _send_admin_report(
    post: Post, success_send: List[dict], error_send: List[dict]
):
    """Вспомогательная функция для отправки отчета админу после публикации"""
    try:
        objects = await db.channel.get_user_channels(
            user_id=post.admin_id, from_array=post.chat_ids
        )

        success_ids = [i.get("chat_id") for i in success_send]
        error_ids = [i.get("chat_id") for i in error_send]

        success_str_inner = "\n".join(
            text("resource_title").format(html.escape(obj.title))
            for obj in objects
            if obj.chat_id in success_ids[:10]
        )
        success_str = (
            f"<blockquote expandable>{success_str_inner}</blockquote>"
            if success_str_inner
            else ""
        )

        error_str_inner = "\n".join(
            text("resource_title").format(html.escape(obj.title))
            + f" \n{''.join(row.get('error') for row in error_send if row.get('chat_id') == obj.chat_id)[:100]}"
            for obj in objects
            if obj.chat_id in error_ids[:10]
        )
        error_str = (
            f"<blockquote expandable>{error_str_inner}</blockquote>"
            if error_str_inner
            else ""
        )

        if success_send and error_send:
            message_text = text("success_error:post:public").format(
                success_str, error_str
            )
        elif success_send:
            message_text = text("manage:post:success:public").format(success_str)
        elif error_send:
            message_text = text("error:post:public").format(error_str)
        else:
            message_text = text("error:post:unknown_notification")

        await bot.send_message(
            chat_id=post.admin_id,
            text=message_text,
            reply_markup=keyboards.posting_menu(),
            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
        )
    except Exception as e:
        logger.error(f"Ошибка отправки отчета админу {post.admin_id}: {e}")

    finally:
        PROCESSING_POSTS.discard(post.id)


@safe_handler("Постинг: отправка отложенных (Background)", log_start=False)
async def send_posts():
    """Периодическая задача: отправка отложенных постов"""

    posts = await db.post.get_post_for_send()

    if posts:
        # Фильтруем посты, которые уже обрабатываются
        new_posts = []
        for p in posts:
            if p.id not in PROCESSING_POSTS:
                new_posts.append(p)
                PROCESSING_POSTS.add(p.id)
            else:
                logger.warning(f"Пост {p.id} уже в процессе отправки, пропускаем")

        posts = new_posts

        if posts:
            logger.info(f"Запущена отправка постов: найдено {len(posts)} новых задач")

    for post in posts:
        asyncio.create_task(send(post))


@safe_handler("Постинг: открепление (Background)", log_start=False)
async def unpin_posts():
    """Периодическая задача: открепление постов"""
    posts = await db.published_post.get_posts_for_unpin()

    for post in posts:
        try:
            await bot.unpin_chat_message(
                chat_id=post.chat_id, message_id=post.message_id
            )
        except Exception as e:
            logger.error(
                f"Ошибка открепления сообщения {post.message_id} в {post.chat_id}: {e}",
                exc_info=True,
            )


@safe_handler("CPM: проверка отчетов (Background)", log_start=False)
async def check_cpm_reports():
    """Периодическая задача: проверка и отправка CPM отчетов за 24/48/72 часа (Агрегированная по post_id)"""
    current_time = int(time.time())

    # 1. Получаем все опубликованные посты с ценой CPM, которые еще не удалены
    stmt = select(PublishedPost).where(
        PublishedPost.cpm_price.is_not(None), PublishedPost.deleted_at.is_(None)
    )
    all_posts = await db.fetch(stmt)
    if not all_posts:
        return

    # 2. Группируем по post_id и определяем, кому нужен отчет
    # post_id -> {period: str, admin_id: int, records: [PublishedPost], cpm_price: int}
    reports_to_send = {}

    # Сначала найдем все post_id, которым нужен отчет сейчас
    for post in all_posts:
        elapsed = current_time - post.created_timestamp
        period = None
        if elapsed >= 72 * 3600 and not post.report_72h_sent:
            period = "72ч"
        elif elapsed >= 48 * 3600 and not post.report_48h_sent:
            period = "48ч"
        elif elapsed >= 24 * 3600 and not post.report_24h_sent:
            period = "24ч"

        if period:
            if post.post_id not in reports_to_send:
                # Берем ВСЕ записи для этого post_id для корректной агрегации
                related = [p for p in all_posts if p.post_id == post.post_id]
                reports_to_send[post.post_id] = {
                    "period": period,
                    "admin_id": post.admin_id,
                    "records": related,
                    "cpm_price": post.cpm_price,
                }

    if not reports_to_send:
        return

    # 3. Собираем данные по каналам для пакетного получения просмотров
    # chat_id -> [message_id, ...]
    chat_batches = {}
    for p_id, data in reports_to_send.items():
        for p in data["records"]:
            if p.chat_id not in chat_batches:
                chat_batches[p.chat_id] = []
            chat_batches[p.chat_id].append(p.message_id)

    # 4. Получаем просмотры пачками по каналам
    # cache[(chat_id, message_id)] = views
    views_cache = {}
    channel_titles = {}  # chat_id -> title

    for chat_id, message_ids in chat_batches.items():
        try:
            v_map, channel = await get_views_for_batch(chat_id, message_ids)
            for mid, v in v_map.items():
                views_cache[(chat_id, mid)] = v
            channel_titles[chat_id] = channel.title
        except Exception as e:
            logger.error(f"Ошибка получения просмотров для канала {chat_id}: {e}")

    # 5. Формируем и отправляем агрегированные отчеты
    for post_id, data in reports_to_send.items():
        try:
            period = data["period"]
            admin_id = data["admin_id"]
            records = data["records"]
            cpm_price = data["cpm_price"]

            # Агрегируем текущие просмотры и исторические данные
            total_current_views = 0
            sum_24 = 0
            sum_48 = 0
            sum_72 = 0
            channels_info = []

            # Обновляем каждую запись в БД и собираем суммы
            for p in records:
                current_views = views_cache.get((p.chat_id, p.message_id), 0)
                total_current_views += current_views

                # Обновление БД для конкретной записи (сохраняем индив. просмотры)
                updates = {}
                if period == "24ч":
                    updates = {"views_24h": current_views, "report_24h_sent": True}
                    p.views_24h = current_views
                elif period == "48ч":
                    updates = {
                        "views_48h": max(current_views, p.views_24h or 0),
                        "report_48h_sent": True,
                    }
                    p.views_48h = updates["views_48h"]
                elif period == "72ч":
                    updates = {
                        "views_72h": max(
                            current_views, p.views_48h or 0, p.views_24h or 0
                        ),
                        "report_72h_sent": True,
                    }
                    p.views_72h = updates["views_72h"]

                stmt = (
                    update(PublishedPost)
                    .where(PublishedPost.id == p.id)
                    .values(**updates)
                )
                await db.execute(stmt)

                # Суммируем для общего отчета
                sum_24 += p.views_24h or 0
                sum_48 += p.views_48h or 0
                sum_72 += p.views_72h or 0

                title = channel_titles.get(p.chat_id, f"Channel {p.chat_id}")
                
                chat_id_str = str(p.chat_id)
                link = f"https://t.me/c/{chat_id_str[4:] if chat_id_str.startswith('-100') else chat_id_str}"
                
                channels_info.append(
                    text("cpm:report:channel_row").format(
                        link, html.escape(title), current_views
                    )
                )

            # Форматирование самого сообщения
            user = await db.user.get_user(admin_id)
            usd_rate = 1.0
            if user and user.default_exchange_rate_id:
                exchange_rate = await db.exchange_rate.get_exchange_rate(
                    user.default_exchange_rate_id
                )
                if exchange_rate and exchange_rate.rate > 0:
                    usd_rate = exchange_rate.rate

            # Превью текста
            representative = records[0]
            opts = representative.message_options or {}
            raw_text = opts.get("text") or opts.get("caption")
            if not raw_text:
                preview_text = text("post:no_text")
            else:
                clean_text = re.sub(r"<[^>]+>", "", raw_text)
                preview_text_raw = (
                    clean_text[:30] + "..." if len(clean_text) > 30 else clean_text
                )
                preview_text = f"«{html.escape(preview_text_raw)}»"

            # Дата публикации
            pub_date = datetime.fromtimestamp(representative.created_timestamp)
            date_str = pub_date.strftime("%d") + " " + text("month").get(str(pub_date.month)) + " " + pub_date.strftime("%Y г.")
            time_str = pub_date.strftime("%H:%M")

            # Сборка строк истории (как в контент плане)
            history_lines = []

            # 24ч
            r24 = round(float(cpm_price * float(sum_24 / 1000)), 2)
            history_lines.append(
                text("cpm:report:history_row").format(
                    "24ч", sum_24, r24, round(r24 / usd_rate, 2)
                )
            )

            # 48ч
            r48 = round(float(cpm_price * float(sum_48 / 1000)), 2)
            history_lines.append(
                text("cpm:report:history_row").format(
                    "48ч", sum_48, r48, round(r48 / usd_rate, 2)
                )
            )

            # 72ч
            r72 = round(float(cpm_price * float(sum_72 / 1000)), 2)
            history_lines.append(
                text("cpm:report:history_row").format(
                    "72ч", sum_72, r72, round(r72 / usd_rate, 2)
                )
            )

            full_report = text("cpm:report:header").format(
                preview_text, date_str, time_str
            ) + "\n"
            full_report += f"💸 <b>CPM:</b> {cpm_price}₽\n"
            full_report += "".join(history_lines)
            full_report += f"\n\nℹ️ <i>Курс: 1 USDT = {round(usd_rate, 2)}₽</i>"

            channels_text = "\n".join(channels_info)
            full_report += f"\n\n{channels_text}"

            # Добавляем подпись
            full_report += await get_report_signatures(user, "cpm", bot)

            await bot.send_message(
                chat_id=admin_id,
                text=full_report,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.error(
                f"Ошибка при обработке агрегированного CPM отчета для post_id {post_id}: {e}",
                exc_info=True,
            )


@safe_handler("Постинг: удаление (Background)", log_start=False)
async def delete_posts():
    """Периодическая задача: удаление постов по расписанию (Пакетная обработка)"""
    db_posts = await db.published_post.get_posts_for_delete()
    if not db_posts:
        return

    # Группируем по chat_id для получения просмотров
    chat_groups = {}
    for post in db_posts:
        if post.chat_id not in chat_groups:
            chat_groups[post.chat_id] = []
        chat_groups[post.chat_id].append(post)

    row_ids = []
    # post_id -> [message_stats] для формирования отчетов админам
    post_reports = {}

    for chat_id, group_posts in chat_groups.items():
        try:
            message_ids = [p.message_id for p in group_posts]
            views_map, channel = await get_views_for_batch(chat_id, message_ids)

            for post in group_posts:
                views = views_map.get(post.message_id, 0)

                # Fallback: Если не удалось получить просмотры (0) или ошибка, берем из БД
                if views == 0:
                    saved_views = [
                        post.views_24h or 0,
                        post.views_48h or 0,
                        post.views_72h or 0,
                    ]
                    views = max(saved_views)
                    if views > 0:
                        logger.warning(
                            f"Использованы сохраненные просмотры ({views}) для поста {post.id} (Live=0)"
                        )

                # Собираем данные для группового отчета админу (по post_id)
                if post.post_id not in post_reports:
                    post_reports[post.post_id] = []

                post_reports[post.post_id].append(
                    {
                        "channel": channel,
                        "views": views,
                        "admin_id": post.admin_id,
                        "cpm_price": post.cpm_price,
                        "post_obj": post,
                    }
                )

                # Удаление из Telegram
                try:
                    await bot.delete_message(post.chat_id, post.message_id)
                except Exception as e:
                    logger.error(
                        f"Ошибка удаления сообщения {post.message_id} в {post.chat_id}: {e}"
                    )
                    try:
                        await bot.send_message(
                            chat_id=post.admin_id,
                            text=text("error:post:delete").format(
                                post.message_id, channel.emoji_id, channel.title
                            ),
                            link_preview_options=types.LinkPreviewOptions(
                                is_disabled=True
                            ),
                        )
                    except Exception as report_err:
                        logger.error(
                            f"Ошибка отправки отчета об ошибке в {post.admin_id}: {report_err}"
                        )

                # Обновление БД перед удалением (записываем финальные просмотры для статистики)
                # Определяем, в какой период (24/48/72ч) попадает текущее время жизни поста
                elapsed_hours = (post.delete_time - post.created_timestamp) / 3600.0
                db_updates = {}

                if elapsed_hours <= 24:
                    if not post.views_24h:
                        db_updates["views_24h"] = views
                elif elapsed_hours <= 48:
                    if not post.views_48h:
                        db_updates["views_48h"] = views
                else:  # > 48
                    if not post.views_72h:
                        db_updates["views_72h"] = views

                if db_updates:
                    from sqlalchemy import update as sqlalchemy_update

                    upd_stmt = (
                        sqlalchemy_update(PublishedPost)
                        .where(PublishedPost.id == post.id)
                        .values(**db_updates)
                    )
                    await db.execute(upd_stmt)

                    # Обновляем объект в памяти для отчета
                    for k, v in db_updates.items():
                        setattr(post, k, v)

                row_ids.append(post.id)
        except Exception as e:
            logger.error(f"Ошибка при пакетном удалении в канале {chat_id}: {e}")

    # Отправка сводных отчетов по каждому post_id (если есть CPM)
    for post_id, message_objects in post_reports.items():
        if not message_objects:
            continue

        cpm_price = message_objects[0]["cpm_price"]
        if not cpm_price:
            continue

        admin_id = message_objects[0]["admin_id"]
        user = await db.user.get_user(admin_id)

        try:
            # Используем общую утилиту для генерации отчета
            report_text = await generate_cpm_report(
                user=user,
                post_id=post_id,
                related_posts=[obj["post_obj"] for obj in message_objects],
                bot=bot
            )

            if not report_text:
                continue

            await bot.send_message(
                chat_id=admin_id,
                text=report_text,
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                reply_markup=Reply.menu(),
            )
        except Exception as e:
            logger.error(
                f"Ошибка отправки CPM отчета админу {admin_id}: {e}", exc_info=True
            )

    await db.published_post.soft_delete_published_posts(row_ids=row_ids)


def register_post_jobs(scheduler: AsyncIOScheduler):
    """
    Регистрация системных периодических задач для постов.

    Использует replace_existing=True для предотвращения дублей при перезапуске.
    """
    # Отправка отложенных постов (каждые 10 секунд)
    scheduler.add_job(
        func=send_posts,
        trigger=CronTrigger(second="*/10"),
        id="send_posts_periodic",
        replace_existing=True,
        name="Отправка отложенных постов",
    )

    # Открепление постов (каждые 10 секунд)
    scheduler.add_job(
        func=unpin_posts,
        trigger=CronTrigger(second="*/10"),
        id="unpin_posts_periodic",
        replace_existing=True,
        name="Открепление постов",
    )

    # Удаление постов (каждые 10 секунд)
    scheduler.add_job(
        func=delete_posts,
        trigger=CronTrigger(second="*/10"),
        id="delete_posts_periodic",
        replace_existing=True,
        name="Удаление постов по расписанию",
    )

    # Проверка CPM отчетов (каждые 10 секунд)
    scheduler.add_job(
        func=check_cpm_reports,
        trigger=CronTrigger(second="*/10"),
        id="check_cpm_reports_periodic",
        replace_existing=True,
        name="Проверка CPM отчетов 24/48/72ч",
    )

    logger.info("Зарегистрированы системные задачи для постов")
