from datetime import datetime
from typing import Dict, Any, Optional

from main_bot.database.db import db
from main_bot.database.db_types import Status
from main_bot.handlers.user.common_content import serialize_channel


def serialize_bot_post(post: Any) -> Optional[Dict[str, Any]]:
    """
    Сериализует объект поста бота в словарь.

    Аргументы:
        post: Объект поста.

    Возвращает:
        dict: Данные поста или None.
    """
    if not post:
        return None
    return {
        "id": post.id,
        "bot_id": getattr(post, "bot_id", None),
        "channel_id": getattr(post, "channel_id", None),
        "message": getattr(post, "message", {}),
        "status": getattr(post, "status", "active"),
        "start_timestamp": post.start_timestamp,
        "end_timestamp": getattr(post, "end_timestamp", None),
        "send_time": getattr(post, "send_time", None),
        "delete_time": getattr(post, "delete_time", None),
        "admin_id": post.admin_id,
        "backup_chat_id": getattr(post, "backup_chat_id", None),
        "backup_message_id": getattr(post, "backup_message_id", None),
        "success_send": getattr(post, "success_send", 0),
        "error_send": getattr(post, "error_send", 0),
        "created_at": getattr(post, "created_at", None),
    }

async def get_days_with_bot_posts(
    bot_id: int, year: int, month: int
) -> Dict[int, Dict[str, bool]]:
    """
    Получает информацию о днях месяца с рассылками и их статусах.

    Аргументы:
        bot_id (int): ID бота (chat_id канала).
        year (int): Год.
        month (int): Месяц.

    Возвращает:
        dict: Словарь {день: {"has_finished": bool, "has_pending": bool}}
    """
    from calendar import monthrange

    _, last_day = monthrange(year, month)
    month_start = datetime(year, month, 1)
    month_end = datetime(year, month, last_day, 23, 59, 59)

    # Получаем все рассылки
    all_month_posts = await db.bot_post.get_bot_posts(bot_id)

    days_info = {}
    for post in all_month_posts:
        timestamp = post.start_timestamp or post.send_time
        if not timestamp:
            continue
        post_date = datetime.fromtimestamp(timestamp)
        if month_start <= post_date <= month_end:
            day = post_date.day
            if day not in days_info:
                days_info[day] = {"has_finished": False, "has_pending": False}

            # Определяем статус
            if post.status == Status.FINISH:
                days_info[day]["has_finished"] = True
            elif post.status == Status.PENDING:
                days_info[day]["has_pending"] = True

    return days_info
