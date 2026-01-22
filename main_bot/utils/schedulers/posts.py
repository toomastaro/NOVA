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
from typing import Dict, List, Optional

from aiogram import types
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select, update

from config import Config
from instance_bot import bot
from main_bot.database.db import db
from main_bot.database.post.model import Post
from main_bot.database.published_post.model import PublishedPost
from main_bot.keyboards import keyboards
from main_bot.keyboards.common import Reply
from main_bot.utils.tg_utils import set_channel_session
from main_bot.utils.lang.language import text
from main_bot.utils.report_signature import get_report_signatures
from main_bot.utils.schemas import MessageOptions
from main_bot.utils.session_manager import SessionManager
from utils.error_handler import safe_handler

logger = logging.getLogger(__name__)


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
    """Отправить пост в каналы"""
    try:
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

        # Очистка опций
        # Грубая очистка - удаляем все конфликтующие поля в зависимости от типа, заново формируем.
        if message_options.text:
            for k in [
                "photo",
                "video",
                "animation",
                "show_caption_above_media",
                "has_spoiler",
                "caption",
            ]:
                options.pop(k, None)
        elif message_options.photo:
            for k in ["video", "animation", "text", "disable_web_page_preview"]:
                options.pop(k, None)
        elif message_options.video:
            for k in ["photo", "animation", "text", "disable_web_page_preview"]:
                options.pop(k, None)
        else:  # animation
            for k in ["photo", "video", "text", "disable_web_page_preview"]:
                options.pop(k, None)

        options["parse_mode"] = "HTML"

        error_send = []
        success_send = []

        # Логика бекапа
        backup_message_id = post.backup_message_id
        if Config.BACKUP_CHAT_ID:
            if not backup_message_id:
                try:
                    options["chat_id"] = Config.BACKUP_CHAT_ID
                    options["parse_mode"] = "HTML"

                    backup_msg = await cor(
                        **options, reply_markup=keyboards.post_kb(post=post)
                    )
                    backup_message_id = backup_msg.message_id

                    await db.post.update_post(
                        post_id=post.id,
                        backup_chat_id=Config.BACKUP_CHAT_ID,
                        backup_message_id=backup_message_id,
                    )
                    logger.info(
                        f"Создан бэкап для поста {post.id}: chat={Config.BACKUP_CHAT_ID}, msg={backup_message_id}"
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка создания бэкапа для поста {post.id}: {e}", exc_info=True
                    )

        for chat_id in post.chat_ids:
            channel = await db.channel.get_channel_by_chat_id(chat_id)
            if not channel or not channel.subscribe:
                continue

            try:
                if backup_message_id and Config.BACKUP_CHAT_ID:
                    post_message = await bot.copy_message(
                        chat_id=chat_id,
                        from_chat_id=Config.BACKUP_CHAT_ID,
                        message_id=backup_message_id,
                        reply_markup=keyboards.post_kb(post=post),
                        parse_mode="HTML",
                    )
                    logger.info(
                        f"Скопирован пост {post.id} (бэкап {backup_message_id}) в {chat_id} (msg {post_message.message_id})"
                    )
                else:
                    options["chat_id"] = chat_id
                    post_message = await cor(
                        **options, reply_markup=keyboards.post_kb(post=post)
                    )
                    logger.info(
                        f"Напрямую отправлен пост {post.id} в {chat_id} (msg {post_message.message_id})"
                    )

                await asyncio.sleep(0.06)
            except Exception as e:
                logger.error(
                    f"Ошибка отправки поста {post.id} в {chat_id}: {e}", exc_info=True
                )
                error_send.append({"chat_id": chat_id, "error": str(e)})
                continue

            if post.pin_time:
                try:
                    await bot.pin_chat_message(
                        chat_id=chat_id,
                        message_id=post_message.message_id,
                        disable_notification=message_options.disable_notification,
                    )
                except Exception as e:
                    logger.error(
                        f"Ошибка закрепления сообщения {post_message.message_id} в {chat_id}: {e}",
                        exc_info=True,
                    )

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
                        post.delete_time + current_time if post.delete_time else None
                    ),
                    "report": post.report,
                    "cpm_price": post.cpm_price,
                    "backup_chat_id": Config.BACKUP_CHAT_ID if backup_message_id else None,
                    "backup_message_id": backup_message_id,
                    "message_options": post.message_options,
                }
            )

        if success_send:
            await db.published_post.add_many_published_post(posts=success_send)

        await db.post.clear_posts(post_ids=[post.id])

        # Если отчет выключен И нет ошибок - выходим.
        # Если есть ошибки - отправляем отчет в любом случае (чтобы не пропустить сбои).
        if not post.report and not error_send:
            return

        objects = await db.channel.get_user_channels(
            user_id=post.admin_id, from_array=post.chat_ids
        )

        # Форматирование списка успешных отправок
        success_str_inner = "\n".join(
            text("resource_title").format(html.escape(obj.title))
            for obj in objects
            if obj.chat_id in [i.get("chat_id") for i in success_send[:10]]
        )
        success_str = (
            f"<blockquote expandable>{success_str_inner}</blockquote>"
            if success_str_inner
            else ""
        )

        # Форматирование списка ошибок
        error_str_inner = "\n".join(
            text("resource_title").format(html.escape(obj.title))
            + f" \n{''.join(row.get('error') for row in error_send[:10] if row.get('chat_id') == obj.chat_id)}"
            for obj in objects
            if obj.chat_id in [i.get("chat_id") for i in error_send[:10]]
        )
        error_str = (
            f"<blockquote expandable>{error_str_inner}</blockquote>"
            if error_str_inner
            else ""
        )

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
            message_text = text("error:post:unknown_notification")

        try:
            await bot.send_message(
                chat_id=post.admin_id,
                text=message_text,
                reply_markup=keyboards.posting_menu(),
                link_preview_options=types.LinkPreviewOptions(is_disabled=True),
            )
        except Exception as e:
            logger.error(
                f"Ошибка отправки отчета админу {post.admin_id}: {e}", exc_info=True
            )

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
    """Периодическая задача: проверка и отправка CPM отчетов за 24/48/72 часа (Пакетная обработка)"""
    current_time = int(time.time())

    # Получаем посты с CPM ценой, которые еще не удалены
    stmt = select(PublishedPost).where(
        PublishedPost.cpm_price.is_not(None), PublishedPost.deleted_at.is_(None)
    )
    posts = await db.fetch(stmt)
    if not posts:
        return

    # Группируем посты по chat_id для минимизации сессий
    groups = {}
    for post in posts:
        elapsed = current_time - post.created_timestamp
        report_needed = False
        period = ""

        if elapsed >= 72 * 3600 and not post.report_72h_sent:
            period = "72ч"
            report_needed = True
        elif elapsed >= 48 * 3600 and not post.report_48h_sent:
            period = "48ч"
            report_needed = True
        elif elapsed >= 24 * 3600 and not post.report_24h_sent:
            period = "24ч"
            report_needed = True

        if report_needed:
            if post.chat_id not in groups:
                groups[post.chat_id] = []
            groups[post.chat_id].append((post, period))

    for chat_id, items in groups.items():
        try:
            message_ids = [p.message_id for p, _ in items]
            views_map, channel = await get_views_for_batch(chat_id, message_ids)

            for post, period in items:
                try:
                    views = views_map.get(post.message_id, 0)
                    
                    # Обновление БД
                    updates = {}
                    if period == "24ч": 
                        updates = {"views_24h": views, "report_24h_sent": True}
                    elif period == "48ч":
                        updates = {"views_48h": max(views, post.views_24h or 0), "report_48h_sent": True}
                    elif period == "72ч":
                        updates = {"views_72h": max(views, post.views_48h or 0, post.views_24h or 0), "report_72h_sent": True}

                    stmt = (
                        update(PublishedPost)
                        .where(PublishedPost.id == post.id)
                        .values(**updates)
                    )
                    await db.execute(stmt)

                    # Отправка отчета
                    cpm_price = post.cpm_price
                    user = await db.user.get_user(post.admin_id)
                    usd_rate = 1.0
                    if user and user.default_exchange_rate_id:
                        exchange_rate = await db.exchange_rate.get_exchange_rate(
                            user.default_exchange_rate_id
                        )
                        if exchange_rate and exchange_rate.rate > 0:
                            usd_rate = exchange_rate.rate

                    channels_text = (
                        text("resource_title").format(html.escape(channel.title))
                        + f" - 👀 {views}"
                    )
                    channels_text = f"<blockquote expandable>{channels_text}</blockquote>"

                    opts = post.message_options or {}
                    raw_text = opts.get("text") or opts.get("caption") or text("post:no_text")
                    clean_text = re.sub(r"<[^>]+>", "", raw_text)
                    preview_text_raw = (
                        clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
                    )
                    preview_text = f"«{html.escape(preview_text_raw)}»"

                    full_report = text("cpm:report:header").format(preview_text, period) + "\n"
                    rub_price = round(float(cpm_price * float(views / 1000)), 2)
                    usd_curr = round(rub_price / usd_rate, 2)
                    full_report += text("cpm:report:history_row").format(
                        period, views, rub_price, usd_curr
                    )
                    full_report += f"\n\nℹ️ <i>Курс: 1 USDT = {round(usd_rate, 2)}₽</i>"
                    full_report += "\n\n" + channels_text

                    # Добавляем подпись
                    full_report += await get_report_signatures(user, "cpm", bot)

                    await bot.send_message(
                        chat_id=post.admin_id,
                        text=full_report,
                        link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                    )
                except Exception as e:
                    logger.error(f"Ошибка при обработке CPM отчета для поста {post.id} в канале {chat_id}: {e}")
        except Exception as e:
            logger.error(f"Ошибка при обработке пакета постов для канала {chat_id}: {e}")


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
                        logger.warning(f"Использованы сохраненные просмотры ({views}) для поста {post.id} (Live=0)")

                # Собираем данные для группового отчета админу (по post_id)
                if post.post_id not in post_reports:
                    post_reports[post.post_id] = []
                
                post_reports[post.post_id].append({
                    "channel": channel,
                    "views": views,
                    "admin_id": post.admin_id,
                    "cpm_price": post.cpm_price,
                    "post_obj": post,
                })

                # Удаление из Telegram
                try:
                    await bot.delete_message(post.chat_id, post.message_id)
                except Exception as e:
                    logger.error(f"Ошибка удаления сообщения {post.message_id} в {post.chat_id}: {e}")
                    try:
                        await bot.send_message(
                            chat_id=post.admin_id,
                            text=text("error:post:delete").format(
                                post.message_id, channel.emoji_id, channel.title
                            ),
                            link_preview_options=types.LinkPreviewOptions(is_disabled=True),
                        )
                    except Exception as report_err:
                        logger.error(f"Ошибка отправки отчета об ошибке в {post.admin_id}: {report_err}")

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
        usd_rate = 1.0

        if user and user.default_exchange_rate_id is not None:
            exchange_rate = await db.exchange_rate.get_exchange_rate(
                user.default_exchange_rate_id
            )
            if exchange_rate and exchange_rate.rate > 0:
                usd_rate = exchange_rate.rate
                # exchange_rate_update_time = exchange_rate.last_update

        total_views = sum(obj["views"] or 0 for obj in message_objects)

        channels_text_inner = "\n".join(
            text("resource_title").format(html.escape(obj["channel"].title))
            + f" - 👀 {obj['views']}"
            for obj in message_objects
        )
        channels_text = f"<blockquote expandable>{channels_text_inner}</blockquote>"

        try:
            representative_post = message_objects[0]["post_obj"]
            delete_duration = (
                representative_post.delete_time - representative_post.created_timestamp
            )
            views_24 = representative_post.views_24h
            views_48 = representative_post.views_48h
            views_72 = representative_post.views_72h

            opts = representative_post.message_options or {}
            raw_text = opts.get("text") or opts.get("caption") or text("post:no_text")
            clean_text = re.sub(r"<[^>]+>", "", raw_text)
            preview_text_raw = (
                clean_text[:50] + "..." if len(clean_text) > 50 else clean_text
            )
            preview_text = f"«{html.escape(preview_text_raw)}»"

            def format_report():
                lines = []
                lines.append(text("cpm:report:header:simple").format(preview_text))

                # 24ч
                v24 = v24_val
                r24 = round(float(cpm_price * float(v24 / 1000)), 2)
                lines.append(text("cpm:report:history_row").format("24ч", v24, r24, round(r24 / usd_rate, 2)))

                # 48ч
                v48 = v48_val
                r48 = round(float(cpm_price * float(v48 / 1000)), 2)
                lines.append(text("cpm:report:history_row").format("48ч", v48, r48, round(r48 / usd_rate, 2)))

                # 72ч
                v72 = v72_val
                r72 = round(float(cpm_price * float(v72 / 1000)), 2)
                lines.append(text("cpm:report:history_row").format("72ч", v72, r72, round(r72 / usd_rate, 2)))

                lines.append(f"\nℹ️ <i>Курс: 1 USDT = {round(usd_rate, 2)}₽</i>")
                lines.append("\n" + channels_text)
                return "\n".join(lines)

            # Приводим к нерасходящемуся виду: каждый следующий период не может быть меньше предыдущего
            v24_val = views_24 if views_24 is not None else 0
            v48_val = max(views_48 if views_48 is not None else 0, v24_val)
            v72_val = max(views_72 if views_72 is not None else 0, v48_val)
            
            # Определяем, какие исторические данные показывать (только если они были зафиксированы)
            hours = int(delete_duration / 3600)
            title = f"{text('cpm:report:final')}: {hours}ч"

            report_text = format_report()

            show_v24 = hours > 24 and views_24 is not None
            show_v48 = hours > 48 and views_48 is not None
            show_v72 = hours > 72 and views_72 is not None

            # Формируем аргументы для format_report
            args_v24 = views_24 if show_v24 else None
            args_v48 = views_48 if show_v48 else None
            args_v72 = views_72 if show_v72 else None

            # Если меньше суточной толерантности, просто Финальный без часов (или с часами)
            # Но по ТЗ: "до 24 часов включительно одна цифра".
            # Если мы передаем None в v24/v48, format_report сам построит одну цифру.

            report_text = format_report(
                title, total_views, args_v24, args_v48, args_v72
            )

            # Добавляем подпись
            report_text += await get_report_signatures(user, "cpm", bot)

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
