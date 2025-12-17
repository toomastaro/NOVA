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
    user_id: int, 
    chosen: List[int], 
    total_days: int, 
    service: str, 
    object_type: str
):
    """
    Выдача подписки на указанные объекты (каналы или боты).
    
    Args:
        user_id: ID пользователя
        chosen: Список ID объектов (row_id в БД)
        total_days: Количество дней подписки
        service: Тип сервиса (top - сортировка)
        object_type: Тип объекта ('channels' или 'bots')
    """
    # Логика извлечена из subscribe_payment.py
    
    added_time = 86400 * total_days
    
    logger.info(f"Выдача подписки пользователю {user_id} на {len(chosen)} объектов типа {object_type} на {total_days} дней")
    
    for obj_id in chosen:
        try:
            if object_type == 'channels':
                channel = await db.channel.get_channel_by_row_id(row_id=obj_id)
                if not channel:
                    logger.warning(f"Канал с ID {obj_id} не найден при выдаче подписки")
                    continue
                
                subscribe_value = channel.subscribe
                if not subscribe_value or subscribe_value < time.time():
                    subscribe_value = added_time + int(time.time())
                else:
                    subscribe_value += added_time

                await db.channel.update_channel_by_chat_id(
                    chat_id=channel.chat_id,
                    subscribe=subscribe_value
                )
                logger.debug(f"Подписка для канала {channel.title} ({channel.id}) обновлена до {subscribe_value}")
                
            else:
                user_bot = await db.user_bot.get_bot_by_id(row_id=obj_id)
                if not user_bot:
                    logger.warning(f"Бот с ID {obj_id} не найден при выдаче подписки")
                    continue
                
                subscribe_value = user_bot.subscribe
                if not subscribe_value or subscribe_value < time.time():
                    subscribe_value = added_time + int(time.time())
                else:
                    subscribe_value += added_time

                await db.user_bot.update_bot_by_id(
                    row_id=user_bot.id,
                    subscribe=subscribe_value
                )
                logger.debug(f"Подписка для бота {user_bot.title} ({user_bot.id}) обновлена до {subscribe_value}")
                
        except Exception as e:
            logger.error(f"Ошибка при выдаче подписки для объекта {obj_id} (тип {object_type}): {e}", exc_info=True)
