from sqlalchemy import text

from hello_bot.database import Base
from hello_bot.database.user.crud import UserCrud
from utils.database_mixin import engine


class Database(
    UserCrud,
):
    """
    Класс для управления базой данных hello_bot.

    Объединяет в себе CRUD-методы для различных сущностей.
    """

    async def create_tables(self):
        """Создает таблицы и схему базы данных."""
        async with engine.begin() as conn:
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self.schema}"'))
            await conn.execute(text(f'SET search_path TO "{self.schema}"'))
            await conn.run_sync(Base.metadata.create_all)

    async def drop_schema(self):
        """Удаляет схему базы данных."""
        async with engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{self.schema}" CASCADE'))
