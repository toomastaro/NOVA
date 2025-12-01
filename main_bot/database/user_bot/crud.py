from sqlalchemy import select, desc, update, insert, delete

from main_bot.database import DatabaseMixin
from main_bot.database.user_bot.model import UserBot


class UserBotCrud(DatabaseMixin):
    async def add_bot(self, **kwargs):
        await self.execute(
            insert(UserBot).values(**kwargs)
        )

    async def get_active_bots(self):
        stmt = (
            select(UserBot)
            .where(UserBot.subscribe.is_not(None))
            .order_by(UserBot.subscribe.asc())
        )
        return await self.fetch(stmt)

    async def get_user_bots(self, user_id: int, limit: int = None, sort_by: bool = None):
        stmt = select(UserBot).where(UserBot.admin_id == user_id)

        if sort_by:
            stmt = stmt.order_by(desc(UserBot.subscribe))
        if limit:
            stmt = stmt.limit(limit)

        return await self.fetch(stmt)

    async def get_bot_by_token(self, token: str) -> UserBot:
        return await self.fetchrow(
            select(UserBot).where(
                UserBot.token == token
            )
        )

    async def get_bot_by_id(self, row_id: int) -> UserBot:
        return await self.fetchrow(
            select(UserBot).where(
                UserBot.id == row_id
            )
        )

    async def delete_bot_by_id(self, row_id: int):
        await self.execute(
            delete(UserBot).where(
                UserBot.id == row_id
            )
        )

    async def update_bot_by_id(self, row_id: int, return_obj: bool = False, **kwargs) -> UserBot | None:
        stmt = update(UserBot).where(UserBot.id == row_id).values(**kwargs)

        if return_obj:
            operation = self.fetchrow
            stmt = stmt.returning(UserBot)
        else:
            operation = self.execute

        return await operation(stmt, **{'commit': return_obj} if return_obj else {})
