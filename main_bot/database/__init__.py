import asyncio
import logging
import time
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Sequence, TypeVar

from config import Config
from sqlalchemy.engine.result import Result
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base
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

# Настройка движка базы данных
engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    pool_size=Config.DB_POOL_SIZE,
    max_overflow=Config.DB_MAX_OVERFLOW,
    pool_timeout=Config.DB_POOL_TIMEOUT,
    pool_pre_ping=True,
)

# Фабрика сессий
async_session = async_sessionmaker(
    bind=engine, expire_on_commit=False, class_=AsyncSession
)

Base = declarative_base()

T = TypeVar("T")

# Константы для retry и таймаутов
DB_TIMEOUT_SECONDS = Config.DB_TIMEOUT_SECONDS
DB_MAX_RETRY_ATTEMPTS = Config.DB_MAX_RETRY_ATTEMPTS


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
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Асинхронный контекстный менеджер для получения сессии базы данных.
    """
    async with async_session() as session:
        yield session


class DatabaseMixin:
    """
    Миксин, предоставляющий базовые методы для работы с базой данных.
    Все методы создают новую сессию для выполнения запроса.
    """

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def execute(sql: Executable, commit: bool = True) -> None:
        """
        Выполняет SQL-запрос.
        :param sql: SQL-запрос (SQLAlchemy statement).
        :param commit: Нужно ли делать коммит (по умолчанию True).
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Executing SQL: {sql}")
                        await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Transaction committed")
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in execute() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in execute(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def execute_many(list_sql: list[Executable]) -> None:
        """
        Выполняет список SQL-запросов в одной транзакции.
        :param list_sql: Список запросов.
        """
        try:
            async with log_slow_query(f"Batch ({len(list_sql)})"):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS * 2):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(
                            f"Executing {len(list_sql)} SQL statements in transaction"
                        )
                        for sql in list_sql:
                            await session.execute(sql)
                        await session.commit()
                        logger.debug("Transaction committed")
        except asyncio.TimeoutError:
            logger.error(
                f"Database timeout in execute_many() after {DB_TIMEOUT_SECONDS * 2}s"
            )
            raise
        except Exception as e:
            logger.error(f"Database error in execute_many(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetch(sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает список скалярных значений (scalars().all()).
        Подходит для выборок списка объектов.
        :param sql: SQL-запрос.
        :return: Список результатов.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Fetching data: {sql}")
                        res: Result = await session.execute(sql)
                        results = res.scalars().all()
                        logger.debug(f"Fetched {len(results)} rows")
                        return results
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in fetch() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in fetch(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchrow(sql: Executable, commit: bool = False) -> Any | None:
        """
        Выполняет запрос и возвращает одну запись (scalar_one_or_none).
        :param sql: SQL-запрос.
        :param commit: Выполнить ли коммит после запроса (например, для RETURNING).
        :return: Один объект или None.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Fetching row: {sql}")
                        res: Result = await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Transaction committed")
                        result = res.scalar_one_or_none()
                        logger.debug(f"Fetched row: {result is not None}")
                        return result
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in fetchrow() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in fetchrow(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchall(sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает все строки (res.all()).
        Возвращает список кортежей (Row).
        :param sql: SQL-запрос.
        :return: Список строк.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Fetching all rows: {sql}")
                        res: Result = await session.execute(sql)
                        results = res.all()
                        logger.debug(f"Fetched {len(results)} rows")
                        return results
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in fetchall() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in fetchall(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def fetchone(sql: Executable) -> Any:
        """
        Выполняет запрос и возвращает ровно одну строку (res.one()).
        Вызовет ошибку, если строк нет или их больше одной.
        :param sql: SQL-запрос.
        :return: Результат.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Fetching one row: {sql}")
                        res: Result = await session.execute(sql)
                        result = res.one()
                        logger.debug("Fetched exactly one row")
                        return result
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in fetchone() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in fetchone(): {e}", exc_info=True)
            raise

    @staticmethod
    @retry(
        retry=retry_if_exception_type((Exception,)),
        stop=stop_after_attempt(DB_MAX_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
    async def add(obj: Any, commit: bool = True) -> Any:
        """
        Добавляет объект в сессию и сохраняет его.
        :param obj: Объект модели SQLAlchemy.
        :param commit: Делать ли коммит.
        :return: Добавленный объект (обновленный).
        """
        try:
            async with log_slow_query(f"Add {obj.__class__.__name__}"):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Adding object: {obj.__class__.__name__}")
                        session.add(obj)
                        if commit:
                            await session.commit()
                            await session.refresh(obj)
                            logger.debug(
                                f"Object added and committed: {obj.__class__.__name__}"
                            )
                        return obj
        except asyncio.TimeoutError:
            logger.error(f"Database timeout in add() after {DB_TIMEOUT_SECONDS}s")
            raise
        except Exception as e:
            logger.error(f"Database error in add(): {e}", exc_info=True)
            raise
