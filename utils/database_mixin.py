"""
Модуль миксина для работы с базой данных.

Содержит абстракцию над SQLAlchemy и asyncpg для выполнения SQL-запросов
с поддержкой повторных попыток (retries) и логирования медленных запросов.
"""

import asyncio
import logging
import time
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Sequence

from config import Config
from sqlalchemy import text
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.sql import Executable
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)

# Кодируем пользователя и пароль
pg_user = urllib.parse.quote_plus(Config.PG_USER)
pg_pass = urllib.parse.quote_plus(Config.PG_PASS)

DATABASE_URL = (
    f"postgresql+asyncpg://{pg_user}:{pg_pass}@{Config.PG_HOST}/{Config.PG_DATABASE}"
)

engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    pool_size=Config.DB_POOL_SIZE,
    max_overflow=Config.DB_MAX_OVERFLOW,
    pool_timeout=Config.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession,
)


@asynccontextmanager
async def log_slow_query(query_info: Any, threshold: float = 1.0):
    """Логирует предупреждение, если выполнение блока занимает больше threshold секунд."""
    start = time.perf_counter()
    try:
        yield
    finally:
        duration = time.perf_counter() - start
        if duration > threshold:
            logger.warning(f"SLOW QUERY ({duration:.3f}s): {query_info}")


@asynccontextmanager
async def get_session(schema: str = None) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        session: AsyncSession
        if schema:
            await session.execute(text(f'SET search_path TO "{schema}"'))
        yield session


# Константы для retry и таймаутов
DB_TIMEOUT_SECONDS = Config.DB_TIMEOUT_SECONDS
DB_MAX_RETRY_ATTEMPTS = Config.DB_MAX_RETRY_ATTEMPTS


class DatabaseMixin:
    """
    Миксин для выполнения SQL-запросов.

    Обертывает вызовы SQLAlchemy с поддержкой:
    - Повторных попыток (tenacity)
    - Логирования медленных запросов
    - Управления транзакциями
    - Обработки таймаутов
    """

    def __init__(self):
        self.schema = None

    def set_schema(self, schema: str):
        self.schema = schema

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def execute(self, sql: Executable, commit: bool = True) -> None:
        """
        Выполняет SQL-запрос без возврата результата.

        :param sql: Объект запроса (SQLAlchemy Executable)
        :param commit: Автоматически коммитить транзакцию (по умолчанию True)
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session(self.schema) as session:
                        session: AsyncSession
                        logger.debug(f"Выполнение SQL (схема={self.schema}): {sql}")
                        await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Транзакция зафиксирована (commit)")
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут базы данных в execute() после {DB_TIMEOUT_SECONDS}с (схема={self.schema})"
            )
            raise
        except Exception as e:
            logger.error(
                f"Ошибка базы данных в execute() (схема={self.schema}): {e}",
                exc_info=True,
            )
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetch(self, sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает список строк (scalars).

        :param sql: Объект запроса
        :return: Список значений (scalars().all())
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session(self.schema) as session:
                        session: AsyncSession
                        logger.debug(f"Получение данных (схема={self.schema}): {sql}")
                        res: Result = await session.execute(sql)
                        results = res.scalars().all()
                        logger.debug(f"Получено строк: {len(results)}")
                        return results
        except asyncio.TimeoutError:
            logger.error(f"Таймаут базы данных в fetch() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка базы данных в fetch(): {e}", exc_info=True)
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchrow(self, sql: Executable, commit: bool = False) -> Any | None:
        """
        Выполняет запрос и возвращает одну строку (или None).

        :param sql: Объект запроса
        :param commit: Коммитить ли транзакцию (редко нужно для select, но бывает)
        :return: Единственное значение (scalar_one_or_none())
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session(self.schema) as session:
                        session: AsyncSession
                        logger.debug(
                            f"Получение одной строки (схема={self.schema}): {sql}"
                        )
                        res: Result = await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Транзакция зафиксирована (commit)")
                        result = res.scalar_one_or_none()
                        return result
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут базы данных в fetchrow() после {DB_TIMEOUT_SECONDS}с"
            )
            raise
        except Exception as e:
            logger.error(f"Ошибка базы данных в fetchrow(): {e}", exc_info=True)
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchall(self, sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает все строки (Result.all()).

        Важно: отличается от fetch тем, что возвращает не скаляры, а кортежи/Row.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session(self.schema) as session:
                        session: AsyncSession
                        logger.debug(
                            f"Получение всех строк (схема={self.schema}): {sql}"
                        )
                        res: Result = await session.execute(sql)
                        results = res.all()
                        logger.debug(f"Получено строк: {len(results)}")
                        return results
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут базы данных в fetchall() после {DB_TIMEOUT_SECONDS}с"
            )
            raise
        except Exception as e:
            logger.error(f"Ошибка базы данных в fetchall(): {e}", exc_info=True)
            raise

    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchone(self, sql: Executable) -> Any:
        """
        Выполняет запрос и возвращает ровно одну строку.

        Если строк нет или их больше одной — вызывает исключение.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session(self.schema) as session:
                        session: AsyncSession
                        logger.debug(
                            f"Получение ровно одной строки (схема={self.schema}): {sql}"
                        )
                        res: Result = await session.execute(sql)
                        result = res.one()
                        return result
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут базы данных в fetchone() после {DB_TIMEOUT_SECONDS}с"
            )
            raise
        except Exception as e:
            logger.error(f"Ошибка базы данных в fetchone(): {e}", exc_info=True)
            raise
