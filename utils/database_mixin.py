from typing import AsyncGenerator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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


@asynccontextmanager
async def get_session(schema: str = None) -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        if schema:
            await session.execute(text(f'SET search_path TO "{schema}"'))
        yield session


class DatabaseMixin:
    def __init__(self):
        self.schema = None

    def set_schema(self, schema: str):
        self.schema = schema

    async def execute(self, sql):
        async with get_session(self.schema) as session:
            session: AsyncSession

            await session.execute(sql)
            await session.commit()

    async def fetch(self, sql):
        async with get_session(self.schema) as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.scalars().all()

    async def fetchrow(self, sql, commit: bool = False):
        async with get_session(self.schema) as session:
            session: AsyncSession

            res = await session.execute(sql)
            if commit:
                await session.commit()

            return res.scalar_one_or_none()

    async def fetchall(self, sql):
        async with get_session(self.schema) as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.all()

    async def fetchone(self, sql):
        async with get_session(self.schema) as session:
            session: AsyncSession

            res = await session.execute(sql)
            return res.one_or_none()
