#!/usr/bin/env python3
"""
Скрипт ожидания готовности базы данных.

Пытается установить соединение с PostgreSQL в цикле.
Используется в Docker-контейнерах перед запуском основных сервисов,
чтобы гарантировать доступность БД.

Запуск:
    python wait-for-db.py
"""

import asyncio
import logging
import os
import sys

import asyncpg

# Настройка простого логирования для скрипта инициализации
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("WaitForDB")


async def wait_for_db():
    """
    Ожидает подключения к базе данных.

    Пытается подключиться к PostgreSQL, используя учетные данные из переменных окружения.
    Делает до `max_retries` попыток с задержкой.

    Возвращает:
        bool: True, если подключение успешно, иначе False.
    """
    max_retries = 30
    retry_count = 0

    pg_user = os.getenv('PG_USER', 'postgres')
    pg_pass = os.getenv('PG_PASS', '')
    pg_db = os.getenv('PG_DATABASE', 'nova_bot_db')
    pg_host = os.getenv('PG_HOST', 'db')
    pg_port = int(os.getenv('PG_PORT', 5432))

    while retry_count < max_retries:
        try:
            conn = await asyncpg.connect(
                user=pg_user,
                password=pg_pass,
                database=pg_db,
                host=pg_host,
                port=pg_port
            )
            await conn.close()
            logger.info("✅ База данных готова к работе!")
            return True
        except Exception as e:
            retry_count += 1
            logger.warning(f"⏳ Ожидание базы данных... ({retry_count}/{max_retries}): {e}")
            await asyncio.sleep(2)

    logger.error("❌ База данных недоступна после максимального количества попыток")
    return False


if __name__ == "__main__":
    success = asyncio.run(wait_for_db())
    sys.exit(0 if success else 1)
