"""
Сервис управления подписками.

Содержит функции для выдачи и продления подписок на доступ к каналам и ботам.
"""

import time
import logging
from typing import List

from main_bot.database.db import db

logger = logging.getLogger(__name__)


async def grant_subscription(
    user_id: int, chosen: List[int], total_days: int, service: str, object_type: str
):
    """
    Выдача подписки на указанные объекты (каналы или боты).

    Args:
        user_id: ID пользователя
        chosen: Список chat_id (для каналов) или id (для ботов)
        total_days: Количество дней подписки
        service: Тип сервиса (например, 'subscribe' или 'stories')
        object_type: Тип объекта ('channels' или 'bots')
    """
    added_seconds = 86400 * total_days
    now = int(time.time())

    logger.info(
        f"Выдача подписки: user_id={user_id}, объектов={len(chosen)}, тип={object_type}, дней={total_days}"
    )

    for obj_id in chosen:
        try:
            if object_type == "channels":
                channel = await db.channel.get_channel_by_chat_id(chat_id=obj_id)
                if not channel:
                    logger.warning(f"Канал {obj_id} не найден при выдаче подписки")
                    continue

                current_sub = channel.subscribe or 0
                new_sub = (max(current_sub, now)) + added_seconds

                await db.channel.update_channel_by_chat_id(
                    chat_id=obj_id, subscribe=new_sub
                )
                logger.debug(f"Подписка канала {obj_id} продлена до {new_sub}")

            else:  # bots
                user_bot = await db.user_bot.get_bot_by_id(row_id=obj_id)
                if not user_bot:
                    logger.warning(f"Бот ID {obj_id} не найден при выдаче подписки")
                    continue

                current_sub = user_bot.subscribe or 0
                new_sub = (max(current_sub, now)) + added_seconds

                await db.user_bot.update_bot_by_id(
                    row_id=obj_id, subscribe=new_sub
                )
                logger.debug(f"Подписка бота {obj_id} продлена до {new_sub}")

        except Exception as e:
            logger.error(
                f"Ошибка выдачи подписки объекту {obj_id} ({object_type}): {e}",
                exc_info=True,
            )
