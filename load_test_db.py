"""
Скрипт для нагрузочного тестирования базы данных.

Выполняет серию запросов к БД с различным уровнем конкурентности
для проверки производительности и настроек пула соединений.

Запуск:
    python load_test_db.py
"""

import asyncio
import logging
import time

from sqlalchemy import text

from config import Config
from main_bot.database import DatabaseMixin
from main_bot.utils.logger import setup_logging

# Настройка логирования через общий модуль
setup_logging()
logger = logging.getLogger(__name__)


class TestDB(DatabaseMixin):
    """Класс для подключения к базе данных в рамках теста."""
    pass


async def benchmark(db: TestDB, concurrency: int, iterations: int):
    """
    Запускает бенчмарк с заданной конкурентностью.

    Аргументы:
        db (TestDB): Экземпляр базы данных.
        concurrency (int): Количество параллельных задач.
        iterations (int): Количество итераций на одну задачу.
    """
    logger.info(f"Старт теста: {concurrency} потоков, {iterations} итераций каждый")
    logger.info(f"Всего запросов: {concurrency * iterations}")

    start_total = time.perf_counter()

    async def worker(worker_id: int):
        try:
            for _ in range(iterations):
                # Простейший запрос SELECT 1 для проверки коннекта
                await db.fetchrow(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Воркер {worker_id} упал: {e}")

    tasks = [worker(i) for i in range(concurrency)]
    await asyncio.gather(*tasks)

    duration = time.perf_counter() - start_total
    total_requests = concurrency * iterations
    rps = total_requests / duration if duration > 0 else 0

    logger.info(f"Завершено за {duration:.4f}s")
    logger.info(f"RPS: {rps:.2f}")
    logger.info("-" * 30)


async def main():
    """Основная функция запуска тестов."""
    logger.info("Инициализация нагрузочного теста...")
    db = TestDB()

    # Прогрев пула соединений
    logger.info("Прогрев пула соединений...")
    try:
        await db.fetchrow(text("SELECT 1"))
        logger.info("Прогрев успешен.")
    except Exception as e:
        logger.error(f"Ошибка прогрева: {e}")
        return

    # Сценарий 1: Низкая нагрузка
    await benchmark(db, concurrency=10, iterations=10)

    # Сценарий 2: Средняя нагрузка
    await benchmark(db, concurrency=50, iterations=20)

    # Сценарий 3: Высокая нагрузка (близко к лимиту пула)
    # Config.DB_POOL_SIZE обычно 30. Проверяем поведение при 100 конкурентных задачах.
    logger.info(f"Тест высокой нагрузки (Concurrency > Pool Size {Config.DB_POOL_SIZE})...")
    await benchmark(db, concurrency=100, iterations=10)


if __name__ == "__main__":
    asyncio.run(main())
