from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import declarative_base

from config import Config


DATABASE_URL = f"postgresql+asyncpg://{Config.PG_USER}:{Config.PG_PASS}@{Config.PG_HOST}/{Config.PG_DATABASE}"
engine = create_async_engine(
    url=DATABASE_URL,
    echo=False,
    pool_size=30,
    max_overflow=10,
    pool_timeout=40,
    pool_pre_ping=True,
)
async_session = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    class_=AsyncSession
)
Base = declarative_base()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        yield session


class DatabaseMixin:
    @staticmethod
    async def execute(sql):
        async with get_session() as session:
            session: AsyncSession

            await session.execute(sql)
            await session.commit()

    @staticmethod
    async def execute_many(list_sql):
        async with get_session() as session:
            session: AsyncSession

            for sql in list_sql:
                await session.execute(sql)

            await session.commit()

    @staticmethod
    async def fetch(sql):
        async with get_session() as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.scalars().all()

    @staticmethod
    async def fetchrow(sql, commit: bool = False):
        async with get_session() as session:
            session: AsyncSession

            res = await session.execute(sql)
            if commit:
                await session.commit()

            return res.scalar_one_or_none()

    @staticmethod
    async def fetchall(sql):
        async with get_session() as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.all()

    @staticmethod
    async def fetchone(sql):
        async with get_session() as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.one()
