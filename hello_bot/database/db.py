from sqlalchemy import text

from hello_bot.database import Base
from hello_bot.database.user.crud import UserCrud
from utils.database_mixin import engine


class Database(
    UserCrud,
):
    async def create_tables(self):
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'))
            await conn.execute(text(f'SET search_path TO "{self.schema}"'))
            await conn.run_sync(Base.metadata.create_all)

    async def drop_schema(self):
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE'))
