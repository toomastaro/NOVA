import asyncio
import logging
import time

from config import Config
from main_bot.database import DatabaseMixin
from sqlalchemy import text

# Настройка логирования для теста
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("LoadTest")

class TestDB(DatabaseMixin):
    pass

async def benchmark(db: TestDB, concurrency: int, iterations: int):
    logger.info(f"Starting benchmark: {concurrency} concurrent tasks, {iterations} iterations each")
    logger.info(f"Total requests: {concurrency * iterations}")
    
    start_total = time.perf_counter()
    
    async def worker(worker_id: int):
        try:
            for _ in range(iterations):
                # Простейший запрос SELECT 1
                await db.fetchrow(text("SELECT 1"))
        except Exception as e:
            logger.error(f"Worker {worker_id} failed: {e}")

    tasks = [worker(i) for i in range(concurrency)]
    await asyncio.gather(*tasks)
    
    duration = time.perf_counter() - start_total
    total_requests = concurrency * iterations
    rps = total_requests / duration
    
    logger.info(f"Finished in {duration:.4f}s")
    logger.info(f"RPS: {rps:.2f}")
    logger.info("-" * 30)

async def main():
    logger.info("Initializing Load Test...")
    db = TestDB()
    
    # Warmup
    logger.info("Warming up connection pool...")
    try:
        await db.fetchrow(text("SELECT 1"))
        logger.info("Warmup successful.")
    except Exception as e:
        logger.error(f"Warmup failed: {e}")
        return

    # Scenario 1: Low load
    await benchmark(db, concurrency=10, iterations=10)

    # Scenario 2: Medium load
    await benchmark(db, concurrency=50, iterations=20)
    
    # Scenario 3: High load (approaching pool limit)
    # Config.DB_POOL_SIZE is usually 30. Checking behavior with 100 concurrent tasks.
    # Tenacity retries should handle pool contention.
    logger.info(f"Testing High Load (Concurrency > Pool Size {Config.DB_POOL_SIZE})...")
    await benchmark(db, concurrency=100, iterations=10)

if __name__ == "__main__":
    asyncio.run(main())
