"""
Пакет базы данных.

Содержит инициализацию асинхронного движка SQLAlchemy, настройки сессий
и базовый класс DatabaseMixin, предоставляющий общие методы для выполнения SQL-запросов.

Переменные:
    engine (AsyncEngine): Асинхронный движок SQLAlchemy.
    async_session (async_sessionmaker): Фабрика асинхронных сессий.
    Base (DeclarativeBase): Базовый класс для моделей.
"""

import asyncio
import logging
import time
import urllib.parse
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Sequence, TypeVar

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

from config import Config

logger = logging.getLogger(__name__)

# Кодирование учетных данных
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

# Константы для повторных попыток
DB_TIMEOUT_SECONDS = Config.DB_TIMEOUT_SECONDS
DB_MAX_RETRY_ATTEMPTS = Config.DB_MAX_RETRY_ATTEMPTS


@asynccontextmanager
async def log_slow_query(query_info: Any, threshold: float = 1.0):
    """
    Контекстный менеджер для логирования медленных запросов.
    
    Если выполнение блока кода занимает более `threshold` секунд,
    выводится предупреждение в лог.

    Аргументы:
        query_info (Any): Информация о запросе (строка или объект SQL).
        threshold (float): Порог времени в секундах.
    """
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
    
    Возвращает:
        AsyncSession: Новая сессия SQLAlchemy.
    """
    async with async_session() as session:
        yield session


class DatabaseMixin:
    """
    Миксин с базовыми методами для работы с БД.

    Предоставляет методы execute, fetch, fetchrow, add с автоматическим
    управлением сессиями, повторными попытками (retry) и логированием.
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

        Аргументы:
            sql (Executable): SQL-запрос (SQLAlchemy statement).
            commit (bool): Выполнять ли commit после запроса.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Выполнение SQL: {sql}")
                        await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Транзакция зафиксирована")
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в execute() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в execute(): {e}", exc_info=True)
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

        Аргументы:
            list_sql (list[Executable]): Список SQL-запросов.
        """
        try:
            async with log_slow_query(f"Batch ({len(list_sql)})"):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS * 2):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(
                            f"Выполнение {len(list_sql)} SQL запросов в транзакции"
                        )
                        for sql in list_sql:
                            await session.execute(sql)
                        await session.commit()
                        logger.debug("Транзакция пакета зафиксирована")
        except asyncio.TimeoutError:
            logger.error(
                f"Таймаут БД в execute_many() после {DB_TIMEOUT_SECONDS * 2}с"
            )
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в execute_many(): {e}", exc_info=True)
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
        Выполняет запрос и возвращает список скалярных значений.

        Аргументы:
            sql (Executable): SQL-запрос.

        Возвращает:
            Sequence[Any]: Список результатов (scalars().all()).
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Получение данных (fetch): {sql}")
                        res: Result = await session.execute(sql)
                        results = res.scalars().all()
                        logger.debug(f"Получено {len(results)} строк")
                        return results
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в fetch() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в fetch(): {e}", exc_info=True)
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
        Выполняет запрос и возвращает одну запись (скаляр).

        Аргументы:
            sql (Executable): SQL-запрос.
            commit (bool): Выполнять ли commit.

        Возвращает:
            Any | None: Результат или None.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Получение строки (fetchrow): {sql}")
                        res: Result = await session.execute(sql)
                        if commit:
                            await session.commit()
                            logger.debug("Транзакция зафиксирована")
                        result = res.scalar_one_or_none()
                        logger.debug(f"Строка получена: {result is not None}")
                        return result
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в fetchrow() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в fetchrow(): {e}", exc_info=True)
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
        Выполняет запрос и возвращает все строки (список кортежей).

        Аргументы:
            sql (Executable): SQL-запрос.

        Возвращает:
            Sequence[Any]: Список строк (Result.all()).
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Получение всех строк (fetchall): {sql}")
                        res: Result = await session.execute(sql)
                        results = res.all()
                        logger.debug(f"Получено {len(results)} строк")
                        return results
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в fetchall() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в fetchall(): {e}", exc_info=True)
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
        Выполняет запрос и возвращает ровно одну строку.
        Вызывает исключение, если строк нет или их > 1.

        Аргументы:
            sql (Executable): SQL-запрос.

        Возвращает:
            Any: Результат.
        """
        try:
            async with log_slow_query(sql):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Получение одной строки (fetchone): {sql}")
                        res: Result = await session.execute(sql)
                        result = res.one()
                        logger.debug("Получена ровно одна строка")
                        return result
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в fetchone() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в fetchone(): {e}", exc_info=True)
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

        Аргументы:
            obj (Any): Объект модели.
            commit (bool): Выполнять ли commit.

        Возвращает:
            Any: Обновленный объект.
        """
        try:
            async with log_slow_query(f"Add {obj.__class__.__name__}"):
                async with asyncio.timeout(DB_TIMEOUT_SECONDS):
                    async with get_session() as session:
                        session: AsyncSession
                        logger.debug(f"Добавление объекта: {obj.__class__.__name__}")
                        session.add(obj)
                        if commit:
                            await session.commit()
                            await session.refresh(obj)
                            logger.debug(
                                f"Объект добавлен и зафиксирован: {obj.__class__.__name__}"
                            )
                        return obj
        except asyncio.TimeoutError:
            logger.error(f"Таймаут БД в add() после {DB_TIMEOUT_SECONDS}с")
            raise
        except Exception as e:
            logger.error(f"Ошибка БД в add(): {e}", exc_info=True)
            raise
