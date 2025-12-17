"""
Планировщик вспомогательных задач.

Этот модуль содержит функции для:
- Обновления курсов валют
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from main_bot.database.db import db
from main_bot.utils.exchange_rates import get_update_of_exchange_rates, get_exchange_rates_from_json

logger = logging.getLogger(__name__)


async def update_exchange_rates_in_db() -> None:
    """
    Периодическая задача: обновление курсов валют в БД.

    Получает актуальные курсы валют из внешнего API и обновляет их в базе данных.
    Если курсы отсутствуют в БД (нет записей), инициализирует их из локального JSON файла.
    """
    # Получение текущего времени по МСК
    last_update = datetime.now(timezone(timedelta(hours=3))).replace(tzinfo=None)

    # Получение новых курсов валют (Retry logic)
    new_update = {}
    for attempt in range(3):
        try:
            new_update = await get_update_of_exchange_rates()
            # Проверяем, что получили хоть один курс > 0
            if any(val > 0 for val in new_update.values()):
                break
        except Exception as e:
            logger.error(f"Попытка {attempt+1} не удалась при получении курсов: {e}")

        logger.warning(f"Попытка {attempt+1}: Все курсы нулевые или ошибка. Повтор через 5с...")
        await asyncio.sleep(5)

    logger.info(f"Получены курсы валют: {new_update}")

    # Проверка наличия курсов в БД
    all_exchange_rate = await db.exchange_rate.get_all_exchange_rate()
    if len(all_exchange_rate) == 0:
        # Инициализация курсов из JSON файла
        json_format_exchange_rate = get_exchange_rates_from_json()
        for exchange_rate in json_format_exchange_rate:
            ed_id = int(exchange_rate["id"])
            await db.exchange_rate.add_exchange_rate(
                id=ed_id,
                name=exchange_rate["name"],
                rate=new_update.get(ed_id, 0.0),
                last_update=last_update
            )
    else:
        # Обновление существующих курсов
        for er_id in new_update.keys():
            if new_update[er_id] != 0:
                await db.exchange_rate.update_exchange_rate(
                    exchange_rate_id=er_id,
                    rate=new_update[er_id],
                    last_update=last_update
                )
