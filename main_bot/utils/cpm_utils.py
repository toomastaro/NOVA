import re
import html
import logging
from datetime import datetime
from main_bot.database.db import db
from main_bot.utils.lang.language import text
from main_bot.utils.report_signature import get_report_signatures

logger = logging.getLogger(__name__)

async def generate_cpm_report(user, post_id, related_posts, bot) -> str:
    """
    Генерирует текст CPM-отчета в новом формате.
    
    :param user: Объект пользователя (админа)
    :param post_id: ID оригинального поста
    :param related_posts: Список объектов PublishedPost
    :param bot: Объект бота
    :return: Отформатированный текст отчета
    """
    if not related_posts:
        return ""

    cpm_price = related_posts[0].cpm_price or 0
    usd_rate = 1.0
    exch_update = text("unknown")

    # Получаем курс валют пользователя
    if user and user.default_exchange_rate_id is not None:
        exchange_rate = await db.exchange_rate.get_exchange_rate(user.default_exchange_rate_id)
        if exchange_rate and exchange_rate.rate > 0:
            usd_rate = exchange_rate.rate
            if exchange_rate.last_update:
                exch_update = exchange_rate.last_update.strftime("%d.%m.%Y %H:%M")

    # Основной пост (для заголовка берем первый)
    main_pp = related_posts[0]
    main_channel = await db.channel.get_channel_by_chat_id(main_pp.chat_id)
    
    # Резюме контента
    opts = main_pp.message_options or {}
    raw_text = opts.get("text") or opts.get("caption") or text("post:no_text")
    clean_text = re.sub(r"<[^>]+>", "", raw_text)
    preview_text = clean_text[:40] + "..." if len(clean_text) > 40 else clean_text
    
    # Дата публикации (из первого поста)
    pub_date = datetime.fromtimestamp(main_pp.created_timestamp)
    date_str = pub_date.strftime("%d") + " " + text("month").get(str(pub_date.month)) + " " + pub_date.strftime("%Y г.")
    time_str = pub_date.strftime("%H:%M")

    # Заголовок
    main_views = max(main_pp.views_24h or 0, main_pp.views_48h or 0, main_pp.views_72h or 0)
    # Используем chat_id для генерации ссылки
    chat_id_str = str(main_channel.chat_id)
    main_link = f"https://t.me/c/{chat_id_str[4:] if chat_id_str.startswith('-100') else chat_id_str}"
    
    report_text = text("cpm:report:header").format(
        html.escape(preview_text),
        date_str,
        time_str,
        html.escape(main_channel.title),
        main_link,
        main_views
    )

    # Список скопированных каналов
    if len(related_posts) > 1:
        report_text += text("cpm:report:copy_header")
        
        # Берем остальные посты (кроме первого)
        other_posts = related_posts[1:]
        max_display = 20
        display_posts = other_posts[:max_display]
        
        for p in display_posts:
            ch = await db.channel.get_channel_by_chat_id(p.chat_id)
            if not ch:
                continue
            
            ch_id_str = str(ch.chat_id)
            ch_link = f"https://t.me/c/{ch_id_str[4:] if ch_id_str.startswith('-100') else ch_id_str}"
            ch_views = max(p.views_24h or 0, p.views_48h or 0, p.views_72h or 0)
            
            # Обрезка длинных названий для компактности как в примере
            ch_title = ch.title[:20] + "..." if len(ch.title) > 23 else ch.title
            
            report_text += "\n" + text("cpm:report:channel_row").format(
                html.escape(ch_title),
                ch_link,
                ch_views
            )
            
        if len(other_posts) > max_display:
            report_text += "\n" + text("cpm:report:more_channels").format(len(other_posts) - max_display)

    # Таймер удаления
    # Ищем максимальный таймер удаления среди постов
    max_del_time = 0
    for p in related_posts:
        if p.delete_time and p.created_timestamp:
            max_del_time = max(max_del_time, (p.delete_time - p.created_timestamp) // 3600)
    
    if max_del_time > 0:
        report_text += text("cpm:report:delete_timer").format(int(max_del_time))

    # Статистика по периодам
    sum_24 = sum(p.views_24h or 0 for p in related_posts)
    sum_48 = sum(p.views_48h or 0 for p in related_posts)
    sum_72 = sum(p.views_72h or 0 for p in related_posts)
    
    # 24ч
    r24 = round(float(cpm_price * float(sum_24 / 1000)), 2)
    report_text += text("cpm:report:stats_block").format(
        "24ч", f"{sum_24:,}", cpm_price, f"{r24:,.2f}", f"{round(r24 / usd_rate, 2):,}", exch_update
    )
    
    # 48ч
    r48 = round(float(cpm_price * float(sum_48 / 1000)), 2)
    report_text += text("cpm:report:stats_block").format(
        "48ч", f"{sum_48:,}", cpm_price, f"{r48:,.2f}", f"{round(r48 / usd_rate, 2):,}", exch_update
    )
    
    # 72ч
    r72 = round(float(cpm_price * float(sum_72 / 1000)), 2)
    report_text += text("cpm:report:stats_block").format(
        "72ч", f"{sum_72:,}", cpm_price, f"{r72:,.2f}", f"{round(r72 / usd_rate, 2):,}", exch_update
    )

    # Подписи
    report_text += await get_report_signatures(user, "cpm", bot)

    return report_text
