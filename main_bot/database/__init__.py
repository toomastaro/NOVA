from typing import AsyncGenerator, Any, Sequence, TypeVar
from contextlib import asynccontextmanager
import urllib.parse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.engine.result import ScalarResult, Result
from sqlalchemy.sql import Executable

from config import Config

# Кодируем пользователя и пароль, чтобы избежать проблем со спецсимволами
pg_user = urllib.parse.quote_plus(Config.PG_USER)
pg_pass = urllib.parse.quote_plus(Config.PG_PASS)

DATABASE_URL = f"postgresql+asyncpg://{pg_user}:{pg_pass}@{Config.PG_HOST}/{Config.PG_DATABASE}"

# Настройка движка базы данных
engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,  # Set True for debug
    pool_size=30,
    max_overflow=10,
    pool_timeout=40,
    pool_pre_ping=True,
)

# Фабрика сессий
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)

Base = declarative_base()

T = TypeVar("T")

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
    async def execute(sql: Executable, commit: bool = True) -> None:
        """
        Выполняет SQL-запрос.
        :param sql: SQL-запрос (SQLAlchemy statement).
        :param commit: Нужно ли делать коммит (по умолчанию True, если встроено в логику, но здесь вызывается commit всегда).
        Прим.: Тут есть session.commit(), так что commit=True подразумевается.
        """
        async with get_session() as session:
            session: AsyncSession

            await session.execute(sql)
            await session.commit()

    @staticmethod
    async def execute_many(list_sql: list[Executable]) -> None:
        """
        Выполняет список SQL-запросов в одной транзакции.
        :param list_sql: Список запросов.
        """
        async with get_session() as session:
            session: AsyncSession

            for sql in list_sql:
                await session.execute(sql)

            await session.commit()

    @staticmethod
    async def fetch(sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает список скалярных значений (scalars().all()).
        Подходит для выборок списка объектов.
        :param sql: SQL-запрос.
        :return: Список результатов.
        """
        async with get_session() as session:
            session: AsyncSession

            res: Result = await session.execute(sql)
            return res.scalars().all()

    @staticmethod
    async def fetchrow(sql: Executable, commit: bool = False) -> Any | None:
        """
        Выполняет запрос и возвращает одну запись (scalar_one_or_none).
        :param sql: SQL-запрос.
        :param commit: Выполнить ли коммит после запроса (например, для RETURNING).
        :return: Один объект или None.
        """
        async with get_session() as session:
            session: AsyncSession

            res: Result = await session.execute(sql)
            if commit:
                await session.commit()

            return res.scalar_one_or_none()

    @staticmethod
    async def fetchall(sql: Executable) -> Sequence[Any]:
        """
        Выполняет запрос и возвращает все строки (res.all()).
        Возвращает список кортежей (Row).
        :param sql: SQL-запрос.
        :return: Список строк.
        """
        async with get_session() as session:
            session: AsyncSession

            res: Result = await session.execute(sql)
            return res.all()

    @staticmethod
    async def fetchone(sql: Executable) -> Any:
        """
        Выполняет запрос и возвращает ровно одну строку (res.one()).
        Вызовет ошибку, если строк нет или их больше одной.
        :param sql: SQL-запрос.
        :return: Результат.
        """
        async with get_session() as session:
            session: AsyncSession

            res: Result = await session.execute(sql)
            return res.one()

    @staticmethod
    async def add(obj: Any, commit: bool = True) -> Any:
        """
        Добавляет объект в сессию и сохраняет его.
        :param obj: Объект модели SQLAlchemy.
        :param commit: Делать ли коммит.
        :return: Добавленный объект (обновленный).
        """
        async with get_session() as session:
            session: AsyncSession
            session.add(obj)
            if commit:
                await session.commit()
                await session.refresh(obj)
            return obj
